# Copyright (c) 2024, info@tridotstech.com and contributors
# For license information, please see license.txt

# import frappe
# from frappe.model.document import Document

# class BudgetTransfer(Document):
# 	pass


import frappe
from frappe.model.document import Document
from frappe.utils import flt

class BudgetTransfer(Document):
    
    def get_source_cc(self):
        query = """
                    SELECT ba.parent, ba.budget_amount, b.name ,b.monthly_distribution
                    FROM `tabBudget Account` ba
                    JOIN `tabGo1 Budget` b ON ba.parent = b.name
                    WHERE ba.account = %s
                        AND b.cost_center = %s
                        AND b.docstatus = 1
                """    
        params = [self.source_gl_account, self.cost_centre]
        if self.source_mandate:
            query += " AND ba.custom_mandate = %s"
            params.append(self.source_mandate)
        source_cc = frappe.db.sql(query, tuple(params), as_dict=True)
        # source_cc = frappe.db.sql("""
        #             SELECT ba.parent, ba.budget_amount, b.name ,b.monthly_distribution
        #             FROM `tabBudget Account` ba
        #             JOIN `tabGo1 Budget` b ON ba.parent = b.name
        #             WHERE ba.account = %s
        #                 AND b.cost_center = %s
        #                 AND ba.custom_mandate =%s
        #                 AND b.docstatus = 1
        #         """, (self.source_gl_account,self.cost_centre,self.source_mandate), as_dict=True)
        
        frappe.log_error("source_cc",source_cc)
        return source_cc
    
    # def get_target_cc(self):
    #     if self.transfer_of_budgets_between_two_gls_of == "Different Cost Centre":
    #         target_cc = frappe.db.sql("""
    #                 SELECT ba.parent, ba.budget_amount ,b.name ,b.monthly_distribution
    #                 FROM `tabBudget Account` ba
    #                 JOIN `tabGo1 Budget` b ON ba.parent = b.name
    #                 WHERE ba.account = %s
    #                     AND b.cost_center = %s
    #                     AND ba.custom_mandate =%s
    #                     AND b.docstatus = 1
    #             """, (self.target_gl_account,self.target_cost_center,self.target_mandate), as_dict=True)
            
    #     elif self.transfer_of_budgets_between_two_gls_of == "Same Cost Centre":
    #         self.target_cost_center = self.cost_centre
    #         target_cc = frappe.db.sql("""
    #                 SELECT ba.parent, ba.budget_amount,b.name ,b.monthly_distribution
    #                 FROM `tabBudget Account` ba
    #                 JOIN `tabGo1 Budget` b ON ba.parent = b.name
    #                 WHERE ba.account = %s
    #                     AND b.cost_center = %s
    #                     AND ba.custom_mandate =%s
    #                     AND b.docstatus = 1
    #             """, (self.target_gl_account,self.cost_centre,self.target_mandate), as_dict=True)
            
    #     frappe.log_error("target_cc",target_cc)
    #     return target_cc
    def get_target_cc(self):
        if self.transfer_of_budgets_between_two_gls_of == "Different Cost Centre":
            query = """
                SELECT ba.parent, ba.budget_amount, b.name, b.monthly_distribution
                FROM `tabBudget Account` ba
                JOIN `tabGo1 Budget` b ON ba.parent = b.name
                WHERE ba.account = %s
                    AND b.cost_center = %s
                    AND b.docstatus = 1
            """
            params = [self.target_gl_account, self.target_cost_center]

            if self.target_mandate:
                query += " AND ba.custom_mandate = %s"
                params.append(self.target_mandate)

            target_cc = frappe.db.sql(query, tuple(params), as_dict=True)

        elif self.transfer_of_budgets_between_two_gls_of == "Same Cost Centre":
            self.target_cost_center = self.cost_centre
            query = """
                SELECT ba.parent, ba.budget_amount, b.name, b.monthly_distribution
                FROM `tabBudget Account` ba
                JOIN `tabGo1 Budget` b ON ba.parent = b.name
                WHERE ba.account = %s
                    AND b.cost_center = %s
                    AND b.docstatus = 1
            """
            params = [self.target_gl_account, self.cost_centre]
            if self.target_mandate:
                query += " AND ba.custom_mandate = %s"
                params.append(self.target_mandate)

            target_cc = frappe.db.sql(query, tuple(params), as_dict=True)

        frappe.log_error("target_cc", target_cc)
        
        return target_cc

    def validate(self):
        self.get_budget_validate()
        # self.validate_cost_centre()
        self.check_debit_amount()
        
    def before_submit(self):
        self.transfer_budget()
        
#########################################################################################################

    def get_budget_validate(self):
        source_cc = self.get_source_cc()
        target_cc = self.get_target_cc()

        if not source_cc or not target_cc:
            frappe.throw("No Source and Target GL Accounts belonging to the same Cost Centre.")

        if len(source_cc) > 1 or len(target_cc) > 1:
            frappe.throw("Check For Mandates.")

        if self.transfer_of_budgets_between_two_gls_of == "Same Cost Centre" and self.source_gl_account == self.target_gl_account and self.source_mandate == self.target_mandate:
            frappe.throw("Source and Target GL Accounts Cannot Be Same.")

        if source_cc and target_cc:
            # frappe.log_error("source_cc",source_cc)
            # frappe.log_error("target_cc",target_cc)
            if self.transfer_of_budgets_between_two_gls_of == "Same Cost Centre":
                if self.cost_centre != self.target_cost_center:
                    frappe.throw("Budget transfer must be within the same cost centre.")
            # self.check_debit_amount(source_amount)

            elif self.transfer_of_budgets_between_two_gls_of == "Different Cost Centre":
                if self.cost_centre == self.target_cost_center:
                    frappe.throw("Budget transfer must be between different cost centers.")
            # self.check_debit_amount(source_amount)
            # self.check_debit_amount(source_amount)
            # self.validate_cost_centre(source_cc,target_cc)   
            #      

    def check_debit_amount(self):
        source_cc = self.get_source_cc()
        source_amount = source_cc[0].get('budget_amount')
        fiscal_year_start_date, fiscal_year_end_date = frappe.db.get_value('Fiscal Year', self.fiscal_year, ['year_start_date', 'year_end_date'])
        
        if self.source_mandate:
            condition3 = " and custom_mandate = %s"
        else:
            condition3 = "and custom_mandate = ''"
        total_debit = frappe.db.sql(f"""
            SELECT SUM(debit) FROM `tabGL Entry`
            WHERE posting_date BETWEEN %s AND %s
            AND account = %s
            {condition3}
        """, (fiscal_year_start_date, fiscal_year_end_date, self.source_gl_account,self.source_mandate))

        if not total_debit or flt(total_debit[0][0]) :
            # source_budget = frappe.db.get_value('Budget Account', {'account': self.source_gl_account}, 'budget_amount',as_dict=1)
            remaining_budget = source_amount - total_debit[0][0]
            frappe.log_error("remaining_budget",remaining_budget)
            
            if remaining_budget< self.amount:
                frappe.throw("Insufficient funds in the source GL account.")
        # else:
        #     frappe.throw("No debits found for the source GL account in the specified fiscal year.")
        # frappe.log_error("total_debit",total_debit)
                
    def transfer_budget(self):
        source_cc = self.get_source_cc()
        target_cc = self.get_target_cc()
        source_gl = frappe.get_doc('Budget Account', {'account': self.source_gl_account,"parent": source_cc[0].get('parent')})
        target_gl = frappe.get_doc('Budget Account', {'account': self.target_gl_account,"parent": target_cc[0].get('parent')})
        if source_gl.budget_amount:
            source_gl.budget_amount = flt(source_gl.budget_amount) - flt(self.amount)
            source_gl.save("Update")
            self.update_month_distribution(source_cc[0].get('monthly_distribution'),source_gl.budget_amount)

        if target_gl.budget_amount:
            target_gl.budget_amount = flt(target_gl.budget_amount) + flt(self.amount)
            target_gl.save("Update")
            self.update_month_distribution(target_cc[0].get('monthly_distribution'),source_gl.budget_amount)

        frappe.db.commit()
        
        frappe.log_error("Updated Source GL Budget Amount",source_gl.budget_amount)
        frappe.log_error("Updated Target GL Budget Amount",target_gl.budget_amount)

    def update_month_distribution(self, monthly_distribution,budget_account):
        total_budget_amount =  budget_account
        monthly_distribution_doc = frappe.get_doc("Monthly Distribution", monthly_distribution)
        for row in monthly_distribution_doc.percentages:
            if row.percentage_allocation != 0:
                custom_amount = (row.percentage_allocation/100)*total_budget_amount
                row.custom_amount = round(flt(custom_amount), 0)
                frappe.log_error("transfer_month_amount",row.custom_amount)
        monthly_distribution_doc.save()