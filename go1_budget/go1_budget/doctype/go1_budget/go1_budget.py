import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, fmt_money, get_last_day, getdate,get_link_to_form

from go1_budget.api import (
	get_custom_accounting_dimensions,
)
from erpnext.accounts.utils import get_fiscal_year
from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account


class BudgetError(frappe.ValidationError):
	pass


class DuplicateBudgetErrormsg(frappe.ValidationError):
	pass


class  Go1Budget(Document):
	def validate(self):
		if not self.get(frappe.scrub(self.budget_against)):
			frappe.throw(_("{0} is mandatory").format(self.budget_against))
		self.validate_duplicate()
		self.validate_accounts()
		self.set_null_value()
		self.validate_applicable_for()

	
	def validate_duplicate(self):
		# frappe.log_error("validate duplicate")
		budget_against_field = frappe.scrub(self.budget_against)
		budget_against = self.get(budget_against_field)

		accounts = [d.account for d in self.accounts] 
		mandates = [d.custom_mandate for d in self.accounts] 
		frappe.log_error("mandates",mandates)
		# frappe.log_error("mandates len",len(mandates))
		frappe.log_error("mandates join",",".join(["%s"] * len(mandates)))
		
		if mandates and any(mandate for mandate in mandates if mandate):
			frappe.log_error("existing_budget with mandate")

			existing_budget = frappe.db.sql(
				"""
				SELECT
					b.name, ba.account, ba.custom_mandate
				FROM
					`tabGo1 Budget` b, `tabBudget Account` ba
				WHERE
					ba.parent = b.name AND b.docstatus < 2 AND b.company = %s AND {} = %s AND
					b.fiscal_year = %s AND b.name != %s AND ba.account IN ({}) AND ba.custom_mandate IN ({})
				""".format(
					budget_against_field, ",".join(["%s"] * len(accounts)), ",".join(["%s"] * len(mandates))
				),
				(self.company, budget_against, self.fiscal_year, self.name, *accounts, *mandates),
				as_dict=1,
			)
			# frappe.log_error("existing_budget with mandate: {}".format(existing_budget))
			for d in existing_budget:
				frappe.throw(
					_(
						"Another Budget record '{0}' already exists against {1} '{2}', account '{3}', and mandate '{4}' for fiscal year {5}"
					).format(d.name, self.budget_against, budget_against, d.account, d.custom_mandate, self.fiscal_year),
					DuplicateBudgetErrormsg,
				)
		else:
			# If no mandates 
			existing_budget = frappe.db.sql(
				"""
				SELECT
					b.name, ba.account
				FROM
					`tabGo1 Budget` b, `tabBudget Account` ba
				WHERE
					ba.parent = b.name AND b.docstatus < 2 AND b.company = %s AND {} = %s AND
					b.fiscal_year = %s AND b.name != %s AND ba.account IN ({}) AND ba.custom_mandate = ""
				""".format(
					budget_against_field, ",".join(["%s"] * len(accounts))
				),
				(self.company, budget_against, self.fiscal_year, self.name, *accounts),
				as_dict=1,
			)
			frappe.log_error("existing_budget",existing_budget)


			for d in existing_budget:
				frappe.log_error("d",d)
				frappe.throw(
					_(
						"Another Budget record '{0}' already exists against {1} '{2}', account '{3}', for fiscal year {4}"
					).format(d.name, self.budget_against, budget_against, d.account, self.fiscal_year),
					DuplicateBudgetErrormsg,
				)


	def validate_accounts(self):
		account_list = []
		for d in self.get("accounts"):
			if d.account:
				account_details = frappe.db.get_value(
					"Account", d.account, ["is_group", "company", "report_type"], as_dict=1
				)

				if account_details.is_group:
					frappe.throw(_("Budget cannot be assigned against Group Account {0}").format(d.account))
				elif account_details.company != self.company:
					frappe.throw(
						_("Account {0} does not belongs to company {1}").format(d.account, self.company)
					)
				elif account_details.report_type != "Profit and Loss":
					frappe.throw(
						_(
							"Budget cannot be assigned against {0}, as it's not an Income or Expense account"
						).format(d.account)
					)

				if d.account in account_list:
					frappe.throw(_("Account {0} has been entered multiple times").format(d.account))
				else:
					account_list.append(d.account)

	def set_null_value(self):
		if self.budget_against == "Cost Center":
			self.project = None
		else:
			self.cost_center = None

	def validate_applicable_for(self):
		if self.applicable_on_material_request and not (
			self.applicable_on_purchase_order and self.applicable_on_booking_actual_expenses
		):
			frappe.throw(
				_("Please enable Applicable on Purchase Order and Applicable on Booking Actual Expenses")
			)

		elif self.applicable_on_purchase_order and not (self.applicable_on_booking_actual_expenses):
			frappe.throw(_("Please enable Applicable on Booking Actual Expenses"))

		elif not (
			self.applicable_on_material_request
			or self.applicable_on_purchase_order
			or self.applicable_on_booking_actual_expenses
		):
			self.applicable_on_booking_actual_expenses = 1

	def before_naming(self):
		self.naming_series = f"{{{frappe.scrub(self.budget_against)}}}./.{self.fiscal_year}/.###"

###########################################################################################################################
def validate_expense_against_budget(args, expense_amount=0):
	args = frappe._dict(args)
	frappe.log_error("args initial",args)
	if not frappe.get_all("Go1 Budget", limit=1):
		return

	if args.get("company") and not args.fiscal_year:
		args.fiscal_year = get_fiscal_year(args.get("posting_date"), company=args.get("company"))[0]
		frappe.flags.exception_approver_role = frappe.get_cached_value(
			"Company", args.get("company"), "exception_budget_approver_role"
		)

	if not frappe.get_cached_value("Go1 Budget", {"fiscal_year": args.fiscal_year, "company": args.company}):  # nosec
		return

	if not args.account:
		args.account = args.get("expense_account")

	if not (args.get("account") and args.get("cost_center")) and args.item_code:
		args.cost_center, args.account = get_item_details(args)

	if not args.account:
		return
	##custom code	
	exempted_gls =  []
	exempted_users = [] 
	budget_setting = frappe.get_doc('Budget Settings', 'Budget Settings')
	for i in budget_setting.budget_control:
		exempted_gls.append(i.account)
	for i in budget_setting.user_not_restricted:
		exempted_users.append(i.user)

	if args.account in exempted_gls:
		frappe.log_error(f"GL Account {args.account} is exempt from budget control.")
		return
	if frappe.session.user in exempted_users:
		frappe.log_error(f"User {frappe.session.user} is exempt from budget control.")
		return
	
	#custom_code 
	if args.voucher_type not in ["Sales Invoice","Purchase Invoice"]:
		if args.voucher_type == 'Expense Claim':
			exp_account = args.account
			q=frappe.db.get_value("Account",exp_account,"root_type")
		else:
			exp_account = args.account
			q=frappe.db.get_value("Account",args.account,"root_type")
		if q == "Expense":
			# pass
			if not check_budget_exists(args.fiscal_year, exp_account, args.cost_center,args.custom_mandate):
				frappe.throw(_("No budget has been set for GL Account {0} or Cost Centre {1} in fiscal year {2}. "
								"Please set a budget before proceeding with any transactions.")
							.format(frappe.bold(exp_account), frappe.bold(args.cost_center), frappe.bold(args.fiscal_year)), BudgetError)
       		#$$$$$$$$$$$$$$
			emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
			employee_gl_mappings = frappe.get_all('Employee GL Mapping', filters={'employee': emp}, fields=['name'])

			for gl_mapping in employee_gl_mappings:
				child_entries = frappe.get_doc('Employee GL Mapping', gl_mapping['name'])

				account_match = False
				costcenter_match = False
				mandate_match = False

				for account_entry in child_entries.glaccount:
					if exp_account in account_entry.account:
						account_match = True
						frappe.log_error("Yes, account match found")
						for costcenter_entry in child_entries.costcenter:
							if args.cost_center in costcenter_entry.cost_center:
								costcenter_match = True
								frappe.log_error("Yes, account and cost center match found")
								if args.custom_mandate:
									for mandate_entry in child_entries.custom_mandate_table:
										if args.custom_mandate in mandate_entry.mandate:
											mandate_match = True
											frappe.log_error("Yes, mandate match found")
											break  
									if mandate_match:
										break 
								else:
									break 
						if costcenter_match:
							break 
				if account_match and costcenter_match and (not args.custom_mandate or mandate_match):
					break
			else:
				frappe.log_error("No match found")
				frappe.throw(_("You are not allowed to consume budget against GL Account {0}, Cost Center {1}{2}.").format(
					frappe.bold(exp_account), 
					frappe.bold(args.cost_center), 
					(", and Mandate {0}".format(args.custom_mandate)) if args.custom_mandate else ""
				), frappe.PermissionError)	
		#
		# Restriction based on Employee GL Mapping
		# emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		# mapped_gl_accounts = frappe.get_all('Employee GL Mapping',
		# 	filters={'employee': emp},
		# 	fields=['gl_account', 'cost_center', 'custom_mandate']
		# )
		# # mapped_gls = {entry['gl_account']: entry['cost_center'] for entry in mapped_gl_accounts}
		# mapped_gls = {(entry['gl_account'], entry['cost_center']): entry['custom_mandate'] for entry in mapped_gl_accounts}
		# # frappe.log_error(title="mapped_gls",message=mapped_gls)
		# # if args.account not in mapped_gls or args.cost_center != mapped_gls.get(args.account):
		# if (args.account, args.cost_center) not in mapped_gls:
		# 	if  (args.custom_mandate and mapped_gls.get((args.account, args.cost_center)) != args.custom_mandate):
		# 		frappe.throw(_("You are not allowed to consume budget against GL Account {0} and Cost Center {1} and Mandate {2} .").format(
		# 			frappe.bold(args.account), frappe.bold(args.cost_center),frappe.bold(args.custom_mandate)
		# 		), frappe.PermissionError)
		# 	else:
		# 		frappe.throw(_("You are not allowed to consume budget against GL Account {0} and Cost Center {1}.").format(
		# 			frappe.bold(args.account), frappe.bold(args.cost_center)
		# 		), frappe.PermissionError)
	##

	default_dimensions = [
		{
			"fieldname": "project",
			"document_type": "Project",
		},
		{
			"fieldname": "cost_center",
			"document_type": "Cost Center",
		},
	]

	for dimension in default_dimensions + get_custom_accounting_dimensions(as_list=False):
		budget_against = dimension.get("fieldname")
		# frappe.log_error("1",budget_against)

		if (
			args.get(budget_against)
			and args.account
			and (frappe.get_cached_value("Account", args.account, "root_type") == "Expense")
		):
			doctype = dimension.get("document_type")

			if frappe.get_cached_value("DocType", doctype, "is_tree"):
				lft, rgt = frappe.get_cached_value(doctype, args.get(budget_against), ["lft", "rgt"])
				condition = f"""and exists(select name from `tab{doctype}`
					where lft<={lft} and rgt>={rgt} and name=b.{budget_against})"""  # nosec
				args.is_tree = True
			else:
				condition = f"and b.{budget_against}={frappe.db.escape(args.get(budget_against))}"
				args.is_tree = False
			frappe.log_error("condition",condition)

			if args.custom_mandate:
				condition1 = f" and ba.custom_mandate='{args.custom_mandate}'"
			else:
				condition1 = ""
				# condition1 = f" and ba.custom_mandate = '' "
			frappe.log_error("conditions",condition1)
			args.budget_against_field = budget_against
			args.budget_against_doctype = doctype

			budget_records = frappe.db.sql(
				f"""
				select
					b.{budget_against} as budget_against, ba.budget_amount, b.monthly_distribution,ba.custom_mandate,
					ifnull(b.applicable_on_material_request, 0) as for_material_request,
					ifnull(applicable_on_purchase_order, 0) as for_purchase_order,
					ifnull(applicable_on_booking_actual_expenses,0) as for_actual_expenses,
					b.action_if_annual_budget_exceeded, b.action_if_accumulated_monthly_budget_exceeded,
					b.action_if_annual_budget_exceeded_on_mr, b.action_if_accumulated_monthly_budget_exceeded_on_mr,
					b.action_if_annual_budget_exceeded_on_po, b.action_if_accumulated_monthly_budget_exceeded_on_po
				from
					`tabGo1 Budget` b, `tabBudget Account` ba
				where
					b.name=ba.parent and b.fiscal_year=%s
					and ba.account=%s and b.docstatus=1
					{condition}
					
					{condition1}
			""",
				(args.fiscal_year, args.account),
				as_dict=True,
			)  # nosec
			frappe.log_error("budget_records",budget_records)
			if budget_records:
				custom_validate_budget_records(args, budget_records, expense_amount)

def custom_validate_budget_records(args, budget_records, expense_amount):
	# frappe.log_error("validate_budget_records")
	#
	budget_settings = frappe.db.get_single_value('Budget Settings', 'budget_based_on')
	frappe.log_error("expense_amount",expense_amount)
	for budget in budget_records:
		if flt(budget.budget_amount):
			frappe.log_error("full",budget.budget_amount)
			amount = expense_amount # oget_amount(args, budget)
			#
			yearly_action, monthly_action, quarterly_action = get_actions(args, budget)
			args["for_material_request"] = budget.for_material_request #new
			args["for_purchase_order"] = budget.for_purchase_order #new

			if budget_settings == "Annual" and yearly_action in ("Stop", "Warn"):
				compare_expense_with_budget(
					args, flt(budget.budget_amount), _("Annual"), yearly_action, budget.budget_against, flt(budget.budget_amount),amount
				)

			if budget_settings == "Monthly" and monthly_action in ["Stop", "Warn"]:
				# frappe.log_error("validate budget records for month")
				budget_amount = get_accumulated_monthly_budget(
					budget.monthly_distribution, args.posting_date, args.fiscal_year, budget.budget_amount,"Monthly",
				)

				args["month_end_date"] = get_last_day(args.posting_date)

				compare_expense_with_budget(
					args, budget_amount, _("Accumulated Monthly"), monthly_action, budget.budget_against,flt(budget.budget_amount), amount
				)
			#
			if budget_settings == "Quarterly" and quarterly_action in ["Stop", "Warn"]:
				frappe.log_error("validate budget records for quarter")
				budget_amount = get_accumulated_monthly_budget(
					budget.monthly_distribution, args.posting_date, args.fiscal_year, budget.budget_amount, "Quarterly"
				)
				frappe.log_error("budget_amount",budget_amount)
				args["quarter_end_date"] = get_quarter_end_date(args.posting_date)
				frappe.log_error("args_quarter_end",args["quarter_end_date"])

				compare_expense_with_budget(
					args,
					budget_amount,
					_("Accumulated Quarterly"),
					quarterly_action,
					budget.budget_against,
					flt(budget.budget_amount),
					amount
					
				)

# Custom_code quarter
def get_quarter_end_date(posting_date):
	# Define quarter end dates for fiscal year (April to March)
	quarter_end_dates = {
		4: '06-30',  # Q1 ends in June
		7: '09-30',  # Q2 ends in September
		10: '12-31', # Q3 ends in December
		1: '03-31',  # Q4 ends in March
	}

	month = getdate(posting_date).month
	if 4 <= month <= 6:
		quarter_end = quarter_end_dates[4]
	elif 7 <= month <= 9:
		quarter_end = quarter_end_dates[7]
	elif 10 <= month <= 12:
		quarter_end = quarter_end_dates[10]
	else:
		quarter_end = quarter_end_dates[1]

	year = getdate(posting_date).year
	if month in (1, 2, 3):
		year += 1

	return get_last_day(f"{year}-{quarter_end}")

#custom_code
def check_budget_exists(fiscal_year, account, cost_center,mandate):
	budget_count = frappe.db.sql("""
		select count(b.name)
		from `tabGo1 Budget` b
		inner join `tabBudget Account` bd on b.name = bd.parent
		where b.fiscal_year = %s and b.cost_center = %s and bd.account = %s and bd.custom_mandate = %s """, 
		(fiscal_year, cost_center, account,mandate))[0][0]
	
	return budget_count > 0


def compare_expense_with_budget(args, budget_amount, action_for, action, budget_against, full_budget,amount=0):
	# args.actual_expense, args.requested_amount, args.ordered_amount = get_actual_expense(args), 0, 0
	frappe.log_error("args0",args)
	args.actual_expense = get_actual_expense(args)
	args.requested_amount = 0
	args.ordered_amount =  0
	if not amount:
		frappe.log_error("amt")
		args.requested_amount, args.ordered_amount = get_requested_amount(args), get_ordered_amount(args)

		if args.get("doctype") == "Material Request" and args.for_material_request:
			amount = args.requested_amount + args.ordered_amount

		elif args.get("doctype") == "Purchase Order" and args.for_purchase_order:
			amount = args.ordered_amount
		else:
			amount = 0
	frappe.log_error("amt",amount)

	# frappe.log_error("actual_expense",actual_expense)
	# total_expense = 0

	# frappe.log_error("expense",total_expense)
	# if args.actual_expense and amount:
	total_expense = args.actual_expense + amount
	frappe.log_error("total_expense",total_expense)

	if total_expense > budget_amount:
		if args.actual_expense > budget_amount:
			error_tense = _("is already")
			diff = args.actual_expense - budget_amount
		else:
			error_tense = _("will be")
			diff = total_expense - budget_amount
			# if getdate(args.posting_date).month == 2:
			# 	action = "Stop"
			

		currency = frappe.get_cached_value("Company", args.company, "default_currency")

		msg = _("{0} Go1 Budget for Account {1} Mandate {7} against {2} {3} is {4}. It {5} exceed by {6}").format(
			_(action_for),
			frappe.bold(args.account),
			frappe.unscrub(args.budget_against_field),
			frappe.bold(budget_against),
			frappe.bold(fmt_money(budget_amount, currency=currency)),
			error_tense,
			frappe.bold(fmt_money(diff, currency=currency)),
			frappe.bold(args.custom_mandate)
		)
		msg += get_expense_breakup(args, currency, budget_against)

		if (
			frappe.flags.exception_approver_role and frappe.flags.exception_approver_role in frappe.get_roles(frappe.session.user)
		):
			action == "Warn" 
		if(flt(args.actual_expense) > flt(full_budget)):
			frappe.log_error("inside message")
			action = "Stop"
			frappe.throw("The expense amount exceeds the available budget. Please review and adjust the expense or budget allocation.", BudgetError, title=_("Budget Exceeded"))

		if action == "Stop":
			frappe.throw(msg, BudgetError, title=_("Budget Exceeded"))
		else:
			frappe.msgprint(msg, indicator="orange", title=_("Budget Exceeded"))

	elif args.amount > budget_amount :
		error_tense = _("will be")
		diff = float(args.amount) - budget_amount
		currency = frappe.get_cached_value("Company", args.company, "default_currency")

		msg = _("{0} Go1 Budget for Account {1} Mandate {7} against {2} {3} is {4}. It {5} exceed by {6}").format(
			_(action_for),
			frappe.bold(args.account),
			frappe.unscrub(args.budget_against_field),
			frappe.bold(budget_against),
			frappe.bold(fmt_money(budget_amount, currency=currency)),
			error_tense,
			frappe.bold(fmt_money(diff, currency=currency)),
			frappe.bold(args.custom_mandate)
		)
		if (
			frappe.flags.exception_approver_role and frappe.flags.exception_approver_role in frappe.get_roles(frappe.session.user)
		):
			action == "Warn" 
		if(flt(args.actual_expense) > flt(full_budget)):
			frappe.log_error("inside message")
			action = "Stop"
			frappe.throw("The expense amount exceeds the available budget. Please review and adjust the expense or budget allocation.", BudgetError, title=_("Budget Exceeded"))

		if action == "Stop":
			frappe.throw(msg, BudgetError, title=_("Budget Exceeded"))
		else:
			frappe.msgprint(msg, indicator="orange", title=_("Budget Exceeded"))




def get_expense_breakup(args, currency, budget_against):
	msg = "<hr>Total Expenses booked through - <ul>"

	common_filters = frappe._dict(
		{
			args.budget_against_field: budget_against,
			"account": args.account,
			"company": args.company,
		}
	)

	msg += (
		"<li>"
		+ frappe.utils.get_link_to_report(
			"General Ledger",
			label="Actual Expenses",
			filters=common_filters.copy().update(
				{
					"from_date": frappe.get_cached_value("Fiscal Year", args.fiscal_year, "year_start_date"),
					"to_date": frappe.get_cached_value("Fiscal Year", args.fiscal_year, "year_end_date"),
					"is_cancelled": 0,
				}
			),
		)
		+ " - "
		+ frappe.bold(fmt_money(args.actual_expense, currency=currency))
		+ "</li>"
	)

	msg += (
		"<li>"
		+ frappe.utils.get_link_to_report(
			"Material Request",
			label="Material Requests",
			report_type="Report Builder",
			doctype="Material Request",
			filters=common_filters.copy().update(
				{
					"status": [["!=", "Stopped"]],
					"docstatus": 1,
					"material_request_type": "Purchase",
					"schedule_date": [["fiscal year", "2023-2024"]],
					"item_code": args.item_code,
					"per_ordered": [["<", 100]],
				}
			),
		)
		+ " - "
		+ frappe.bold(fmt_money(args.requested_amount, currency=currency))
		+ "</li>"
	)

	msg += (
		"<li>"
		+ frappe.utils.get_link_to_report(
			"Purchase Order",
			label="Unbilled Orders",
			report_type="Report Builder",
			doctype="Purchase Order",
			filters=common_filters.copy().update(
				{
					"status": [["!=", "Closed"]],
					"docstatus": 1,
					"transaction_date": [["fiscal year", "2023-2024"]],
					"item_code": args.item_code,
					"per_billed": [["<", 100]],
				}
			),
		)
		+ " - "
		+ frappe.bold(fmt_money(args.ordered_amount, currency=currency))
		+ "</li></ul>"
	)

	return msg


def get_actions(args, budget):
	yearly_action = budget.action_if_annual_budget_exceeded
	monthly_action = budget.action_if_accumulated_monthly_budget_exceeded
	quarterly_action = budget.action_if_accumulated_monthly_budget_exceeded

	if args.get("doctype") == "Material Request" and budget.for_material_request:
		yearly_action = budget.action_if_annual_budget_exceeded_on_mr
		monthly_action = budget.action_if_accumulated_monthly_budget_exceeded_on_mr
		quarterly_action = budget.action_if_accumulated_monthly_budget_exceeded_on_mr


	elif args.get("doctype") == "Purchase Order" and budget.for_purchase_order:
		yearly_action = budget.action_if_annual_budget_exceeded_on_po
		monthly_action = budget.action_if_accumulated_monthly_budget_exceeded_on_po
		quarterly_action = budget.action_if_accumulated_monthly_budget_exceeded_on_po
	
	return yearly_action, monthly_action,quarterly_action


def get_requested_amount(args):
	item_code = args.get("item_code")
	condition = get_other_condition(args, "Material Request")

	data = frappe.db.sql(
		""" select ifnull((sum(child.stock_qty - child.ordered_qty) * rate), 0) as amount
		from `tabMaterial Request Item` child, `tabMaterial Request` parent where parent.name = child.parent and
		child.item_code = %s and parent.docstatus = 1 and child.stock_qty > child.ordered_qty and {} and
		parent.material_request_type = 'Purchase' and parent.status != 'Stopped'""".format(condition),
		item_code,
		as_list=1,
	)
	frappe.log_error("data",data)
	return data[0][0] if data else 0


def get_ordered_amount(args):
	item_code = args.get("item_code")
	condition = get_other_condition(args, "Purchase Order")

	data = frappe.db.sql(
		f""" select ifnull(sum(child.amount - child.billed_amt), 0) as amount
		from `tabPurchase Order Item` child, `tabPurchase Order` parent where
		parent.name = child.parent and child.item_code = %s and parent.docstatus = 1 and child.amount > child.billed_amt
		and parent.status != 'Closed' and {condition}""",
		item_code,
		as_list=1,
	)
	frappe.log_error("data",data)

	return data[0][0] if data else 0


def get_other_condition(args, for_doc):
	condition = "expense_account = '%s'" % (args.expense_account)
	budget_against_field = args.get("budget_against_field")

	if budget_against_field and args.get(budget_against_field):
		condition += f" and child.{budget_against_field} = '{args.get(budget_against_field)}'"

	if args.get("fiscal_year"):
		date_field = "schedule_date" if for_doc == "Material Request" else "transaction_date"
		start_date, end_date = frappe.db.get_value(
			"Fiscal Year", args.get("fiscal_year"), ["year_start_date", "year_end_date"]
		)

		condition += f""" and parent.{date_field}
			between '{start_date}' and '{end_date}' """

	return condition


def get_actual_expense(args):
	frappe.log_error(title="budget_against_doctype",message=args.budget_against_doctype)
	if not args.budget_against_doctype:
		args.budget_against_doctype = frappe.unscrub(args.budget_against_field)

	budget_against_field = args.get("budget_against_field")
	frappe.log_error(title="budget_against_field",message=budget_against_field)

	# condition1 = " and gle.posting_date <= %(month_end_date)s" if args.get("month_end_date") else ""
	condition1 = ""
	if args.get("month_end_date"):
		condition1 = " and gle.posting_date <= %(month_end_date)s"
	elif args["quarter_end_date"]:
		condition1 = " and gle.posting_date <= %(quarter_end_date)s"
	frappe.log_error(title="consition1",message=condition1)



	if args.is_tree:
		lft_rgt = frappe.db.get_value(
			args.budget_against_doctype, args.get(budget_against_field), ["lft", "rgt"], as_dict=1
		)

		args.update(lft_rgt)

		condition2 = f"""and exists(select name from `tab{args.budget_against_doctype}`
			where lft>=%(lft)s and rgt<=%(rgt)s
			and name=gle.{budget_against_field})"""
		frappe.log_error("condition2",message=condition2)
	else:
		condition2 = f"""and exists(select name from `tab{args.budget_against_doctype}`
		where name=gle.{budget_against_field} and
		gle.{budget_against_field} = %({budget_against_field})s)"""

	condition3 = ""
	if args.custom_mandate:
		condition3 = " and gle.custom_mandate = %(custom_mandate)s"
	else:
		condition3 = "and gle.custom_mandate = ''"
		
		
	amount = flt(
		frappe.db.sql(
			f"""
		select sum(gle.debit) - sum(gle.credit)
		from `tabGL Entry` gle
		where
			is_cancelled = 0
			and gle.account=%(account)s
			{condition1}
			and gle.fiscal_year=%(fiscal_year)s
			and gle.company=%(company)s
			and gle.docstatus=1
			{condition2}
			{condition3}
	""",
			(args),
		)[0][0]  
	)  # nosec
	frappe.log_error(title="ammount",message=amount)
	return amount


def get_accumulated_monthly_budget(monthly_distribution, posting_date, fiscal_year, annual_budget,period=""):
	distribution = {}
	if monthly_distribution:
		for d in frappe.db.sql(
			f"""select mdp.month, mdp.percentage_allocation
			from `tabMonthly Distribution Percentage` mdp, `tabMonthly Distribution` md
			where mdp.parent=md.name and md.fiscal_year='{fiscal_year}' and md.name = '{monthly_distribution}' """,
			as_dict=1,
		):
			distribution.setdefault(d.month, d.percentage_allocation)
	frappe.log_error("123")
	dt = frappe.db.get_value("Fiscal Year", fiscal_year, "year_start_date")
	accumulated_percentage = 0.0

	if period == "Monthly":
		while dt <= getdate(posting_date):
			if monthly_distribution:
				accumulated_percentage += distribution.get(getdate(dt).strftime("%B"), 0)
			else:
				accumulated_percentage += 100.0 / 12

			dt = add_months(dt, 1)

	elif period == "Quarterly":
		frappe.log_error("get_accumulated_monthly_budget for quarter")
		quarters = {
			1: ['April', 'May', 'June'],   # Q1
			2: ['July', 'August', 'September'],  # Q2
			3: ['October', 'November', 'December'],  # Q3
			4: ['January', 'February', 'March'],  # Q4
		}

		current_month = getdate(posting_date).month
		if 4 <= current_month <= 6:
			current_quarter = 1
		elif 7 <= current_month <= 9:
			current_quarter = 2
		elif 10 <= current_month <= 12:
			current_quarter = 3
		else:
			current_quarter = 4

		for quarter in range(1, current_quarter + 1):
			for month_name in quarters[quarter]:
				accumulated_percentage += distribution.get(month_name, 0) if monthly_distribution else 100.0 / 4
				# if current_month != 3 and month_name != 'March':
					# accumulated_percentage += distribution.get(month_name, 0) if monthly_distribution else 100.0 / 4
				# if current_month == 3:
				# 	accumulated_percentage += distribution.get(month_name, 0) if monthly_distribution else 100.0 / 4
		# for month_name in quarters[current_quarter]:
			# accumulated_percentage += distribution.get(month_name, 0) if monthly_distribution else 100.0 / 4
		frappe.log_error(title="annual_budget",message=annual_budget)
		frappe.log_error(title="accumulated_percentage",message=accumulated_percentage)
		msg=annual_budget*accumulated_percentage/100
		frappe.log_error(title="msg",message=msg)


	return annual_budget * accumulated_percentage / 100



def get_item_details(args):
	cost_center, expense_account = None, None

	if not args.get("company"):
		return cost_center, expense_account

	if args.item_code:
		item_defaults = frappe.db.get_value(
			"Item Default",
			{"parent": args.item_code, "company": args.get("company")},
			["buying_cost_center", "expense_account"],
		)
		if item_defaults:
			cost_center, expense_account = item_defaults

	if not (cost_center and expense_account):
		for doctype in ["Item Group", "Company"]:
			data = get_expense_cost_center(doctype, args)

			if not cost_center and data:
				cost_center = data[0]

			if not expense_account and data:
				expense_account = data[1]

			if cost_center and expense_account:
				return cost_center, expense_account

	return cost_center, expense_account


def get_expense_cost_center(doctype, args):
	if doctype == "Item Group":
		return frappe.db.get_value(
			"Item Default",
			{"parent": args.get(frappe.scrub(doctype)), "company": args.get("company")},
			["buying_cost_center", "expense_account"],
		)
	else:
		return frappe.db.get_value(
			doctype, args.get(frappe.scrub(doctype)), ["cost_center", "default_expense_account"]
		)

def custom_validate_budget(doc,method=None):
		frappe.log_error("validate budget")
		if doc.docstatus == 1:
			for data in doc.get("items"):
				args = data.as_dict()
				args.update(
					{
						"doctype": doc.doctype,
						"company": doc.company,
						"posting_date": (
							doc.schedule_date
							if doc.doctype == "Material Request"
							else doc.transaction_date
						),
					}
				)

				validate_expense_against_budget(args)
	
	
#journal Entry
def build_gl_map(doc, method=None):
    frappe.log_error("build_gl_map")
    gl_map = []
    
    for d in doc.get("accounts"):
        if d.debit or d.credit or (doc.voucher_type == "Exchange Gain Or Loss"):
            r = [d.user_remark, doc.remark]
            r = [x for x in r if x]
            remarks = "\n".join(r)

            gl_dict = {
                "account": d.account,
                "party_type": d.party_type,
                "due_date": doc.due_date,
                "party": d.party,
                "against": d.against_account,
                "debit": flt(d.debit, d.precision("debit")),
                "credit": flt(d.credit, d.precision("credit")),
                "account_currency": d.account_currency,
                "debit_in_account_currency": flt(d.debit_in_account_currency, d.precision("debit_in_account_currency")),
                "credit_in_account_currency": flt(d.credit_in_account_currency, d.precision("credit_in_account_currency")),
                "against_voucher_type": d.reference_type,
                "against_voucher": d.reference_name,
                "remarks": remarks,
                "voucher_detail_no": d.reference_detail_no,
                "cost_center": d.cost_center,
                "project": d.project,
                "finance_book": doc.finance_book,
            }

            # Include custom_mandate only if it has a value
            if d.custom_mandate:
                gl_dict["custom_mandate"] = d.custom_mandate

            gl_map.append(doc.get_gl_dict(gl_dict, item=d))

    if gl_map:
        frappe.log_error("gl_map", gl_map)
        for entry in gl_map:
            validate_expense_against_budget(entry)

# def build_gl_map(doc,method=None):
# 		frappe.log_error("build_gl_map")
# 		gl_map = []
# 		for d in doc.get("accounts"):
# 			if d.debit or d.credit or (doc.voucher_type == "Exchange Gain Or Loss"):
# 				r = [d.user_remark, doc.remark]
# 				r = [x for x in r if x]
# 				remarks = "\n".join(r)

# 				gl_map.append(
# 					doc.get_gl_dict(
# 						{
# 							"account": d.account,
# 							"custom_mandate":d.custom_mandate,
# 							"party_type": d.party_type,
# 							"due_date": doc.due_date,
# 							"party": d.party,
# 							"against": d.against_account,
# 							"debit": flt(d.debit, d.precision("debit")),
# 							"credit": flt(d.credit, d.precision("credit")),
# 							"account_currency": d.account_currency,
# 							"debit_in_account_currency": flt(
# 								d.debit_in_account_currency, d.precision("debit_in_account_currency")
# 							),
# 							"credit_in_account_currency": flt(
# 								d.credit_in_account_currency, d.precision("credit_in_account_currency")
# 							),
# 							"against_voucher_type": d.reference_type,
# 							"against_voucher": d.reference_name,
# 							"remarks": remarks,
# 							"voucher_detail_no": d.reference_detail_no,
# 							"cost_center": d.cost_center,
# 							"project": d.project,
# 							"finance_book": doc.finance_book,
# 						},
# 						item=d,
# 					)
# 				)
# 		if gl_map:
# 			frappe.log_error("gl_map",gl_map)
# 			for entry in gl_map:
# 				validate_expense_against_budget(entry)



# def get_gl_entries(doc,method=None):
# 		gl_entry = []
# 		doc.validate_account_details()
# 		q = doc.validate_account_details()
# 		frappe.log_error("q",q)
# 		# payable entry
# 		if doc.grand_total:
# 			gl_entry.append(
# 				doc.get_gl_dict(
# 					{
# 						# "account":",".join([d.default_account for d in doc.expenses]),
# 						"account":doc.payable_account,
# 						"actual_expense": doc.grand_total,
# 						"credit_in_account_currency": doc.grand_total,
# 						"against": ",".join([d.default_account for d in doc.expenses]),
# 						"party_type": "Employee",
# 						"party": doc.employee,
# 						"against_voucher_type": doc.doctype,
# 						"against_voucher": doc.name,
# 						"cost_center": doc.cost_center,
# 						"custom_mandate":",".join([d.custom_mandate for d in doc.expenses]),
# 						"project": doc.project,
# 					},
# 					item=doc,
# 				)
# 			)

# 		# expense entries
# 		for data in doc.expenses:
# 			gl_entry.append(
# 				doc.get_gl_dict(
# 					{
# 						"account": data.default_account,
# 						"actual_expense": data.sanctioned_amount,
# 						"debit_in_account_currency": data.sanctioned_amount,
# 						"against": doc.employee,
# 						"cost_center": data.cost_center or doc.cost_center,
# 						"custom_mandate":data.custom_mandate,
# 						"project": data.project or doc.project,
# 					},
# 					item=data,
# 				)
# 			)
# 			frappe.log_error(title="data",message=data.default_account)
#Expense Claim
def get_gl_entries(doc, method=None):
		gl_entry = []
		doc.validate_account_details()
		q = doc.validate_account_details()
		frappe.log_error("q", q)

		# Payable entry
		if doc.grand_total:
			gl_dict = {
				"account": doc.payable_account,
				"actual_expense": doc.grand_total,
				"credit_in_account_currency": doc.grand_total,
				"against": ",".join([d.default_account for d in doc.expenses]),
				"party_type": "Employee",
				"party": doc.employee,
				"against_voucher_type": doc.doctype,
				"against_voucher": doc.name,
				"cost_center": doc.cost_center,
				"project": doc.project,
			}

			# Add custom_mandate only if it's not empty
			custom_mandates = [d.custom_mandate for d in doc.expenses if d.custom_mandate]
			if custom_mandates:
				gl_dict["custom_mandate"] = ",".join(custom_mandates)

			gl_entry.append(doc.get_gl_dict(gl_dict, item=doc))

		# Expense entries
		for data in doc.expenses:
			gl_dict = {
				"account": data.default_account,
				"actual_expense": data.sanctioned_amount,
				"debit_in_account_currency": data.sanctioned_amount,
				"against": doc.employee,
				"cost_center": data.cost_center or doc.cost_center,
				"project": data.project or doc.project,
			}

			# Add custom_mandate only if it's not empty
			if data.custom_mandate:
				gl_dict["custom_mandate"] = data.custom_mandate

			gl_entry.append(doc.get_gl_dict(gl_dict, item=data))
			frappe.log_error(title="data", message=data.default_account)

    # return gl_entry

		for data in doc.advances:
			gl_entry.append(
				doc.get_gl_dict(
					{
						"account": data.advance_account,
						"credit": data.allocated_amount,
						"credit_in_account_currency": data.allocated_amount,
						"against": ",".join([d.default_account for d in doc.expenses]),
						"party_type": "Employee",
						"party": doc.employee,
						"against_voucher_type": "Employee Advance",
						"against_voucher": data.employee_advance,
					}
				)
			)

		doc.add_tax_gl_entries(gl_entry)
		q1 = doc.add_tax_gl_entries(gl_entry)

		if doc.is_paid and doc.grand_total:
			# payment entry
			payment_account = get_bank_cash_account(doc.mode_of_payment, doc.company).get("account")
			gl_entry.append(
				doc.get_gl_dict(
					{
						"account": payment_account,
						"credit": doc.grand_total,
						"credit_in_account_currency": doc.grand_total,
						"against": doc.employee,
					},
					item=doc,
				)

			)

			gl_entry.append(
				doc.get_gl_dict(
					{
						"account": doc.payable_account,
						"party_type": "Employee",
						"party": doc.employee,
						"against": payment_account,
						"debit": doc.grand_total,
						"debit_in_account_currency": doc.grand_total,
						"against_voucher": doc.name,
						"against_voucher_type": doc.doctype,
					},
					item=doc,
				)
			)

		if gl_entry:
			frappe.log_error("q1",gl_entry)
			for entry in gl_entry:
				frappe.log_error(title="entry",message=entry)
				validate_expense_against_budget(entry)
	



def validate_account_details(doc):
		for data in doc.expenses:
			if not data.cost_center:
				frappe.throw(
					_("Row {0}: {1} is required in the expenses table to book an expense claim.").format(
						data.idx, frappe.bold(_("Cost Center"))
					)
				)
			# if not data.custom_mandate:
			# 	frappe.throw(
			# 		_("Row {0}: {1} is required in the expenses table to book an expense claim.").format(
			# 			data.idx, frappe.bold(_("Mandate"))
			# 		)
			# 	)

		if doc.is_paid:
			if not doc.mode_of_payment:
				frappe.throw(_("Mode of payment is required to make a payment").format(doc.employee))


	
def add_tax_gl_entries(doc, gl_entries):
		# tax table gl entries
		for tax in doc.get("taxes"):
			gl_entries.append(
				doc.get_gl_dict(
					{
						"account": tax.account_head,
						"debit": tax.tax_amount,
						"debit_in_account_currency": tax.tax_amount,
						"against": doc.employee,
						"cost_center": tax.cost_center or doc.cost_center,
						"project": tax.project or doc.project,
						"against_voucher_type": doc.doctype,
						"against_voucher": doc.name,
					},
					item=tax,
				)
			)

def get_bank_cash_account(mode_of_payment, company):
	account = frappe.db.get_value(
		"Mode of Payment Account", {"parent": mode_of_payment, "company": company}, "default_account"
	)
	if not account:
		frappe.throw(
			_("Please set default Cash or Bank account in Mode of Payment {0}").format(
				get_link_to_form("Mode of Payment", mode_of_payment)
			),
			title=_("Missing Account"),
		)
	return {"account": account}

#for monthly distribution
# @frappe.whitelist()
# def calc_percent(self, method):
#     total = 0
#     for row in self.percentages:
#         if self.custom_distribution_based_on == "Manual Amount" and row.custom_amount < 0:
#             frappe.throw("Amount cannot be negative")
#         total += row.custom_amount
#     frappe.log_error("total",total)
#     for row in self.percentages:
#         if row.custom_amount != 0:
#             row.percentage_allocation = (row.custom_amount/total)*100
			