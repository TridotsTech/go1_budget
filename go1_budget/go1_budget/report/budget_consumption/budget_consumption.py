# import frappe

# def execute(filters=None):
#     columns, data = get_columns(), get_data(filters)
#     return columns, data

# def get_columns():
#     return [
#         {"fieldname": "cost_center", "label": "Cost Center", "fieldtype": "Data", "width": 400},
#         {"fieldname": "budget_amount", "label": "Budget Amount", "fieldtype": "Currency", "width": 150},
#         # {"fieldname": "mandate", "label": "Mandate", "fieldtype": "Link", "options": "Mandate", "width": 150},
#         {"fieldname": "material_requests", "label": "Material Requests", "fieldtype": "Currency", "width": 150},
#         {"fieldname": "purchase_orders", "label": "Purchase Orders", "fieldtype": "Currency", "width": 150},
#         {"fieldname": "purchase_receipts", "label": "Purchase Receipts", "fieldtype": "Currency", "width": 150},
#         {"fieldname": "purchase_invoices", "label": "Purchase Invoices", "fieldtype": "Currency", "width": 150},
#     ]

# def get_data(filters):
#     conditions = []
#     params = {}

#     if filters.get("from_date"):
#         conditions.append("mr.transaction_date >= %(from_date)s")
#         params["from_date"] = filters["from_date"]

#     if filters.get("to_date"):
#         conditions.append("mr.transaction_date <= %(to_date)s")
#         params["to_date"] = filters["to_date"]

#     if filters.get("account"):
#         conditions.append("mri.expense_account = %(account)s")
#         params["account"] = filters["account"]

#     if filters.get("cost_center"):
#         conditions.append("mri.cost_center = %(cost_center)s")
#         params["cost_center"] = filters["cost_center"]

#     if filters.get("mandate"):
#         conditions.append("mri.custom_mandate = %(mandate)s")
#         params["mandate"] = filters["mandate"]

#     if filters.get("project"):
#         conditions.append("mri.project = %(project)s")
#         params["project"] = filters["project"]

#     condition_str = " AND ".join(conditions) if conditions else ""


#     sql_query = f"""
#     SELECT 
#         b.cost_center AS cost_center,
#         ba.account AS expense_account,
#         ba.custom_mandate AS mandate,
#         mri.project AS project,
#         ba.budget_amount AS budget_amount,
#         COALESCE(SUM(CASE 
#                 WHEN po.name IS NULL THEN mri.amount
#                 WHEN po.name IS NOT NULL THEN (mri.amount - poi.amount)
#                 ELSE 0
#             END), 0) AS material_requests,
#         SUM(CASE 
#                 WHEN po.name IS NOT NULL AND pr.name IS NULL THEN poi.amount
#                 WHEN pr.name IS NOT NULL THEN (poi.amount - pri.amount)
#                 ELSE 0
#             END) AS purchase_orders,
#         SUM(CASE 
#                 WHEN pr.name IS NOT NULL AND pi.name IS NULL THEN pri.amount
#                 WHEN pi.name IS NOT NULL THEN (pri.amount - pii.amount)
#                 ELSE 0
#             END) AS purchase_receipts,
#         SUM(CASE 
#                 WHEN pi.name IS NOT NULL THEN pii.amount
#                 ELSE 0
#             END) AS purchase_invoices
#     FROM 
#         `tabGo1 Budget` b
#     LEFT JOIN
#         `tabBudget Account` ba ON b.name = ba.parent
#     LEFT JOIN 
#         `tabMaterial Request Item` mri ON mri.cost_center = b.cost_center AND mri.expense_account = ba.account 
#            AND mri.custom_mandate = ba.custom_mandate AND mri.docstatus = 1
#     LEFT JOIN 
#         `tabMaterial Request` mr ON mr.name = mri.parent AND mr.docstatus = 1
#     LEFT JOIN 
#         `tabPurchase Order Item` poi ON poi.material_request = mr.name AND poi.docstatus = 1
#     LEFT JOIN 
#         `tabPurchase Order` po ON po.name = poi.parent AND po.docstatus = 1
#     LEFT JOIN 
#         `tabPurchase Receipt Item` pri ON pri.purchase_order = po.name AND pri.docstatus = 1
#     LEFT JOIN 
#         `tabPurchase Receipt` pr ON pr.name = pri.parent AND pr.docstatus = 1
#     LEFT JOIN 
#         `tabPurchase Invoice Item` pii ON pii.purchase_receipt = pr.name AND pii.docstatus = 1
#     LEFT JOIN 
#         `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
#     WHERE 
#         b.docstatus = 1
#          {(" AND " + condition_str) if condition_str else ""}
#     GROUP BY 
#         b.cost_center, ba.account,COALESCE(ba.custom_mandate)
#     """

#     budget_query = frappe.db.sql(sql_query, params, as_dict=True)
#     frappe.log_error("budget_query",budget_query)
#     output = []
#     cost_center_totals = {}

#     cost_centers = []
#     accounts = []

#     for row in budget_query:
#         if row['cost_center'] not in cost_center_totals:
#             frappe.log_error("row", row['purchase_orders'])
#             cost_center_totals[row['cost_center']] = {
#                 'budget_amount': row['budget_amount'] or 0,
#                 'material_requests': row['material_requests'] or 0,
#                 'purchase_orders': row['purchase_orders'] or 0,
#                 'purchase_receipts': row['purchase_receipts'] or 0,
#                 'purchase_invoices': row['purchase_invoices'] or 0
#             }
#         else:
#             cost_center_totals[row['cost_center']]['budget_amount'] += row['budget_amount'] or 0
#             cost_center_totals[row['cost_center']]['material_requests'] += row['material_requests'] or 0
#             cost_center_totals[row['cost_center']]['purchase_orders'] +=  row['purchase_orders'] or 0
#             cost_center_totals[row['cost_center']]['purchase_receipts'] +=  row['purchase_receipts'] or 0
#             cost_center_totals[row['cost_center']]['purchase_invoices'] += row['purchase_invoices'] or 0
            
#     for row in budget_query:
#         if row.cost_center not in cost_centers:
#             cost_centers.append(row['cost_center'])
#             accounts = [row['expense_account']]
#             total_values = cost_center_totals[row['cost_center']]
#             frappe.log_error("Totals",total_values)
#             output.append({
#             "cost_center": row['cost_center'],
#             "budget_amount": total_values['budget_amount'],
#             "material_requests": total_values['material_requests'],
#             "purchase_orders": total_values['purchase_orders'],
#             "purchase_receipts": total_values['purchase_receipts'],
#             "purchase_invoices": total_values['purchase_invoices'],
#             "indent": 0
#             })
#             output.append({
#             "cost_center": row['expense_account'],
#             "budget_amount": row['budget_amount'],
#             "material_requests": row['material_requests'],
#             "purchase_orders": row['purchase_orders'],
#             "purchase_receipts": row['purchase_receipts'],
#             "purchase_invoices": row['purchase_invoices'],
#             "indent": 1
#         })
#             if row.mandate:
#                 frappe.log_error("mandate",row['budget_amount'])
#                 output.append({
#                 "cost_center": row['mandate'],
#                 "budget_amount": row['budget_amount'],
#                 "material_requests": row['material_requests'],
#                 "purchase_orders": row['purchase_orders'],
#                 "purchase_receipts": row['purchase_receipts'],
#                 "purchase_invoices": row['purchase_invoices'],
#                 "indent": 2
#             })
#         else:
#             if row['expense_account'] not in accounts:
#                 accounts.append(row['expense_account'])
#                 output.append({
#                     "cost_center": row['expense_account'],
#                     "budget_amount": row['budget_amount'],
#                     "material_requests": row['material_requests'],
#                     "purchase_orders": row['purchase_orders'],
#                     "purchase_receipts": row['purchase_receipts'],
#                     "purchase_invoices": row['purchase_invoices'],
#                     "indent": 1
#                 })
#                 if row.mandate:
#                     output.append({
#                         "cost_center": row['mandate'],
#                         "budget_amount": row['budget_amount'],
#                         "material_requests": row['material_requests'],
#                         "purchase_orders": row['purchase_orders'],
#                         "purchase_receipts": row['purchase_receipts'],
#                         "purchase_invoices": row['purchase_invoices'],
#                         "indent": 2
#                     })
#             else:
#                 if row.mandate:
#                     output.append({
#                         "cost_center": row['mandate'],
#                         "budget_amount": row['budget_amount'],
#                         "material_requests": row['material_requests'],
#                         "purchase_orders": row['purchase_orders'],
#                         "purchase_receipts": row['purchase_receipts'],
#                         "purchase_invoices": row['purchase_invoices'],
#                         "indent": 2
#                     })

#     frappe.log_error("cost_center_totals",cost_center_totals)
#     frappe.log_error("output",output)

#     return output

import frappe

def execute(filters=None):
    columns, data = get_columns(), get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "cost_center", "label": "Cost Center", "fieldtype": "Data", "width": 400},
        {"fieldname": "budget_amount", "label": "Budget Amount", "fieldtype": "Currency", "width": 150},
        # {"fieldname": "mandate", "label": "Mandate", "fieldtype": "Link", "options": "Mandate", "width": 150},
        {"fieldname": "material_requests", "label": "Material Requests", "fieldtype": "Currency", "width": 150},
        {"fieldname": "purchase_orders", "label": "Purchase Orders", "fieldtype": "Currency", "width": 150},
        {"fieldname": "purchase_receipts", "label": "Purchase Receipts", "fieldtype": "Currency", "width": 150},
        {"fieldname": "purchase_invoices", "label": "Purchase Invoices", "fieldtype": "Currency", "width": 150},
        {"fieldname": "balance_amount", "label": "Balance Amount", "fieldtype": "Currency", "width": 150},
    ]

def get_data(filters):
    conditions = []
    params = {}

    if filters.get("from_date"):
        conditions.append("mr.transaction_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("mr.transaction_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]

    if filters.get("account"):
        conditions.append("mri.expense_account = %(account)s")
        params["account"] = filters["account"]

    if filters.get("cost_center"):
        conditions.append("mri.cost_center = %(cost_center)s")
        params["cost_center"] = filters["cost_center"]

    if filters.get("mandate"):
        conditions.append("mri.custom_mandate = %(mandate)s")
        params["mandate"] = filters["mandate"]

    if filters.get("project"):
        conditions.append("mri.project = %(project)s")
        params["project"] = filters["project"]

    condition_str = " AND ".join(conditions) if conditions else ""

    sql_query = f"""
    SELECT 
        b.cost_center AS cost_center,
        ba.account AS expense_account,
        ba.custom_mandate AS mandate,
        mri.project AS project,
        ba.budget_amount AS budget_amount,
        COALESCE(SUM(CASE 
                WHEN po.name IS NOT NULL AND poi.material_request = mr.name THEN (mri.amount - poi.amount)
                WHEN poi.material_request IS NULL THEN mri.amount
                WHEN po.name IS NULL THEN mri.amount
                ELSE 0
            END),0) AS material_requests,
        SUM(CASE   
                WHEN po.name IS NOT NULL AND pr.name IS NULL THEN poi.amount
                WHEN pr.name IS NOT NULL THEN (poi.amount - pri.amount)
                ELSE 0
            END) AS purchase_orders,
        SUM(CASE 
                WHEN pr.name IS NOT NULL AND pi.name IS NULL THEN pri.amount
                WHEN pi.name IS NOT NULL THEN (pri.amount - pii.amount)
                ELSE 0
            END) AS purchase_receipts,
        SUM(CASE 
                WHEN pi.name IS NOT NULL THEN pii.amount
                ELSE 0
            END) AS purchase_invoices
    FROM 
        `tabGo1 Budget` b
    LEFT JOIN
        `tabBudget Account` ba ON b.name = ba.parent
    LEFT JOIN 
        `tabMaterial Request Item` mri ON mri.cost_center = b.cost_center AND mri.expense_account = ba.account 
           AND mri.custom_mandate = ba.custom_mandate AND mri.docstatus = 1
    LEFT JOIN 
        `tabMaterial Request` mr ON mr.name = mri.parent AND mr.docstatus = 1
    LEFT JOIN 
        `tabPurchase Order Item` poi ON (poi.material_request = mr.name OR poi.material_request IS NULL) AND poi.expense_account = ba.account AND poi.custom_mandate = ba.custom_mandate AND poi.docstatus = 1
    LEFT JOIN 
        `tabPurchase Order` po ON po.name = poi.parent AND po.docstatus = 1
    LEFT JOIN 
        `tabPurchase Receipt Item` pri ON pri.purchase_order = po.name AND pri.docstatus = 1
    LEFT JOIN 
        `tabPurchase Receipt` pr ON pr.name = pri.parent AND pr.docstatus = 1
    LEFT JOIN 
        `tabPurchase Invoice Item` pii ON pii.purchase_receipt = pr.name AND pii.docstatus = 1
    LEFT JOIN 
        `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 1
    WHERE 
        b.docstatus = 1
        {(" AND " + condition_str) if condition_str else ""}
    GROUP BY 
        b.cost_center, ba.account, COALESCE(ba.custom_mandate)
    """

    budget_query = frappe.db.sql(sql_query, params, as_dict=True)
    frappe.log_error("budget_query", budget_query)
    output = []
    cost_center_totals = {}
    account_totals = {}
    cost_centers = []
    accounts = []


    for row in budget_query:
        if row['cost_center'] not in cost_center_totals:
            cost_center_totals[row['cost_center']] = {
                'budget_amount': row['budget_amount'] or 0,
                'material_requests': row['material_requests'] or 0,
                'purchase_orders': row['purchase_orders'] or 0,
                'purchase_receipts': row['purchase_receipts'] or 0,
                'purchase_invoices': row['purchase_invoices'] or 0
            }
        else:
            cost_center_totals[row['cost_center']]['budget_amount'] += row['budget_amount'] or 0
            cost_center_totals[row['cost_center']]['material_requests'] += row['material_requests'] or 0
            cost_center_totals[row['cost_center']]['purchase_orders'] += row['purchase_orders'] or 0
            cost_center_totals[row['cost_center']]['purchase_receipts'] += row['purchase_receipts'] or 0
            cost_center_totals[row['cost_center']]['purchase_invoices'] += row['purchase_invoices'] or 0

        # if row['expense_account'] not in account_totals:
        #     account_totals[row['expense_account']] = {
        #         'budget_amount': row['budget_amount'] or 0,
        #         'material_requests': row['material_requests'] or 0,
        #         'purchase_orders': row['purchase_orders'] or 0,
        #         'purchase_receipts': row['purchase_receipts'] or 0,
        #         'purchase_invoices': row['purchase_invoices'] or 0
        #     }
        # else:
        #     account_totals[row['expense_account']]['budget_amount'] += row['budget_amount'] or 0
        #     account_totals[row['expense_account']]['material_requests'] += row['material_requests'] or 0
        #     account_totals[row['expense_account']]['purchase_orders'] += row['purchase_orders'] or 0
        #     account_totals[row['expense_account']]['purchase_receipts'] += row['purchase_receipts'] or 0
        #     account_totals[row['expense_account']]['purchase_invoices'] += row['purchase_invoices'] or 0
        # frappe.log_error("account_totals",account_totals)

    for row in budget_query:
        if row['cost_center'] not in cost_centers:
            cost_centers.append(row['cost_center'])
            accounts = [row['expense_account']]
            total_values = cost_center_totals[row['cost_center']]
            # total_account_values = account_totals[row['expense_account']]
           
            output.append({
                "cost_center": row['cost_center'],
                "budget_amount": total_values['budget_amount'],
                "material_requests": total_values['material_requests'],
                "purchase_orders": total_values['purchase_orders'],
                "purchase_receipts": total_values['purchase_receipts'],
                "purchase_invoices": total_values['purchase_invoices'],
                "balance_amount": total_values['budget_amount'] - (
                total_values['material_requests'] +
                total_values['purchase_orders'] +
                total_values['purchase_receipts'] +
                total_values['purchase_invoices']
            ),
                "indent": 0
            })
            output.append({
                "cost_center": row['expense_account'],
                "budget_amount": row['budget_amount'],
                "material_requests": row['material_requests'],
                "purchase_orders": row['purchase_orders'],
                "purchase_receipts": row['purchase_receipts'],
                "purchase_invoices": row['purchase_invoices'],
                "balance_amount": row['budget_amount'] - (
                    row['material_requests'] +
                    row['purchase_orders'] +
                    row['purchase_receipts'] +
                    row['purchase_invoices']
                ),
                "indent": 1
            })
            if row['mandate']:
                output.append({
                    "cost_center": row['mandate'],
                    "budget_amount": row['budget_amount'],
                    "material_requests": row['material_requests'],
                    "purchase_orders": row['purchase_orders'],
                    "purchase_receipts": row['purchase_receipts'],
                    "purchase_invoices": row['purchase_invoices'],
                    "balance_amount": row['budget_amount'] - (
                        row['material_requests'] +
                        row['purchase_orders'] +
                        row['purchase_receipts'] +
                        row['purchase_invoices']
                    ),
                    "indent": 2
                })
        else:
            if row['expense_account'] not in accounts:
                accounts.append(row['expense_account'])
                output.append({
                    "cost_center": row['expense_account'],
                    "budget_amount": row['budget_amount'],
                    "material_requests": row['material_requests'],
                    "purchase_orders": row['purchase_orders'],
                    "purchase_receipts": row['purchase_receipts'],
                    "purchase_invoices": row['purchase_invoices'],
                    "balance_amount": row['budget_amount'] - (
                        row['material_requests'] +
                        row['purchase_orders'] +
                        row['purchase_receipts'] +
                        row['purchase_invoices']
                    ),
                    "indent": 1
                })
                if row['mandate']:
                    output.append({
                        "cost_center": row['mandate'],
                        "budget_amount": row['budget_amount'],
                        "material_requests": row['material_requests'],
                        "purchase_orders": row['purchase_orders'],
                        "purchase_receipts": row['purchase_receipts'],
                        "purchase_invoices": row['purchase_invoices'],
                        "balance_amount": row['budget_amount'] - (
                            row['material_requests'] +
                            row['purchase_orders'] +
                            row['purchase_receipts'] +
                            row['purchase_invoices']
                        ),
                        "indent": 2
                    })
            else:
                for entry in output:
                    if entry['cost_center'] == row['expense_account'] and entry['indent'] == 1:
                        # Update the existing values by adding the new values
                        entry['budget_amount'] += row['budget_amount'] or 0
                        entry['material_requests'] += row['material_requests'] or 0
                        entry['purchase_orders'] += row['purchase_orders'] or 0
                        entry['purchase_receipts'] += row['purchase_receipts'] or 0
                        entry['purchase_invoices'] += row['purchase_invoices'] or 0
                        entry['balance_amount'] = entry['budget_amount'] - (
                            entry['material_requests'] +
                            entry['purchase_orders'] +
                            entry['purchase_receipts'] +
                            entry['purchase_invoices']
                        )
                
                if row['mandate']:
                    output.append({
                        "cost_center": row['mandate'],
                        "budget_amount": row['budget_amount'],
                        "material_requests": row['material_requests'],
                        "purchase_orders": row['purchase_orders'],
                        "purchase_receipts": row['purchase_receipts'],
                        "purchase_invoices": row['purchase_invoices'],
                        "balance_amount": row['budget_amount'] - (
                            row['material_requests'] +
                            row['purchase_orders'] +
                            row['purchase_receipts'] +
                            row['purchase_invoices']
                        ),
                        "indent": 2
                    })

    frappe.log_error("cost_center_totals", cost_center_totals)
    frappe.log_error("output", output)

    return output



