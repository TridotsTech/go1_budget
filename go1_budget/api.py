import frappe
from frappe.utils import flt

@frappe.whitelist()
def update_monthly_distribution(self, method):
    frappe.log_error("calling monthly")
    total_budget_amount =  self.accounts[0].budget_amount
    monthly_distribution_doc = frappe.get_doc("Monthly Distribution", self.monthly_distribution)
    for row in monthly_distribution_doc.percentages:
         if row.percentage_allocation != 0:
            custom_amount = (row.percentage_allocation/100)*total_budget_amount
            row.custom_amount = round(flt(custom_amount), 0)
            frappe.log_error("custom_amount",row.custom_amount)
    monthly_distribution_doc.save()

@frappe.whitelist()
def calc_budget(self, method):
    total_budget_amount = sum(account.budget_amount for account in self.accounts)
    # frappe.log_error("total_budget_amount",total_budget_amount)
    manual_amount_total = 0
    if self.monthly_distribution:
        monthly_distribution_doc = frappe.get_doc("Monthly Distribution", self.monthly_distribution)
        if monthly_distribution_doc.custom_distribution_based_on == "Manual Amount":
            manual_amount_total = sum(distribution.custom_amount for distribution in monthly_distribution_doc.percentages)
    # frappe.log_error("manual_amount_total",manual_amount_total)
    if monthly_distribution_doc.custom_distribution_based_on == "Manual Amount" and total_budget_amount != manual_amount_total and not self.amended_from:
         frappe.throw("Total budget amount does not match the monthly distriution total!")

@frappe.whitelist()
def calc_percent(self, method):
    total = 0
    for row in self.percentages:
        if self.custom_distribution_based_on == "Manual Amount" and row.custom_amount < 0:
            frappe.throw("Amount cannot be negative")
        total += row.custom_amount
    frappe.log_error("total",total)
    for row in self.percentages:
        if row.custom_amount != 0:
            row.percentage_allocation = (row.custom_amount/total)*100

@frappe.whitelist()
def get_custom_accounting_dimensions(as_list=True, filters=None):
	if not filters:
		filters = {"disabled": 0}

	if frappe.flags.accounting_dimensions is None:
		frappe.flags.accounting_dimensions = frappe.get_all(
			"Accounting Dimension",
			fields=["label", "fieldname", "disabled", "document_type"],
			filters=filters,
		)

	if as_list:
		return [d.fieldname for d in frappe.flags.accounting_dimensions]
	else:
		return frappe.flags.accounting_dimensions


@frappe.whitelist()
def get_gl_accounts(doctype, txt, searchfield, start, page_len, filters):
    cost_center = filters.get('cost_center')
    
    return frappe.db.sql("""
        SELECT budget.account
        FROM `tabBudget Account` budget
        JOIN `tabIris Budget` b ON b.name = budget.parent
        WHERE b.cost_center = %s 
        AND b.docstatus = 1
    """, (cost_center))
