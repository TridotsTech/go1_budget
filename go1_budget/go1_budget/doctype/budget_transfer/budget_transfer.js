// Copyright (c) 2024, info@tridotstech.com and contributors
// For license information, please see license.txt

// frappe.ui.form.on('Budget Transfer', {
// 	// refresh: function(frm) {

// 	// }
// });
frappe.ui.form.on('Budget Transfer', {
	transfer_of_budgets_between_two_gls_of: function(frm) {
        if (frm.doc.transfer_of_budgets_between_two_gls_of === "Different Cost Centre") {
            frm.set_value("naming_series", "DCC-.YYYY.-");
            
        }else{
            frm.set_value("naming_series", "SCC-.YYYY.-");
            
        }
    },
    cost_centre:function(frm){
            if(frm.doc.transfer_of_budgets_between_two_gls_of == "Same Cost Centre"){

                frm.set_value('target_cost_center', frm.doc.cost_centre);
                frm.set_query('target_gl_account', () => {
                    return {
                        query: "go1_budget.api.get_gl_accounts", 
                        filters: {
                            cost_center: frm.doc.cost_centre
                        }
                    };
                });
            }
            frm.set_query('source_gl_account', () => {
                return {
                    query: "go1_budget.api.get_gl_accounts", 
                    filters: {
                        cost_center: frm.doc.cost_centre
                    }
                };
            });
     },
    target_cost_center:function(frm){
        if(frm.doc.transfer_of_budgets_between_two_gls_of == "Different Cost Centre"){
            frm.set_query('target_gl_account', () => {
                return {
                    query: "go1_budget.api.get_gl_accounts", 
                    filters: {
                        cost_center: frm.doc.target_cost_center
                    }
                };
            });
        }
    },
    refresh: function(frm) {
        frm.add_custom_button(__('Check Function'), function() {
            frappe.call({
                method: 'go1_budget.custom_buying_controller.check_function',
                callback: function(r) {
                    if (r) {
                        
                        console.log(r);
                    }
                }
            });
        });
    }
});
