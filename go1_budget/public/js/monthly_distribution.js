frappe.ui.form.on('Monthly Distribution', {
    custom_distribution_based_on:function(frm) {
        console.log("INN")
        if (frm.doc.custom_distribution_based_on == 'Manual Amount') {
            for (var row of cur_frm.get_field("percentages").grid.grid_rows){
                row.columns.percentage_allocation.df.read_only = 1
                row.doc.percentage_allocation = 0
            }
        }else if(frm.doc.custom_distribution_based_on == 'Percentage') {
            for (var row of cur_frm.get_field("percentages").grid.grid_rows){
                row.columns.amount.df.read_only = 1
                // row.columns.amount.df.hidden = 1
            }
        }
         frm.refresh_field('percentages');
    },
    onload(frm) {
        if (frm.doc.__islocal) {
            console.log(frm.doc)
            return frm.call({
                method: "iris_budget.api.get_months1",
                args: {
                    "doc": frm.doc
                },
                callback: function(r) {
                    console.log(r.message)
                    if (r.message) {
                        frm.clear_table("percentages");
                        for (var d of r.message){
                            let row = frm.add_child("percentages");
                            row.month = d.month;
                            row.percentage_allocation = d.percentage_allocation;
                            row.custom_amount = 0;
                            row.idx = d.idx;
                        }
                        frm.refresh_field("percentages");
                    }
                }
            });
        }
    },

    refresh(frm) {
        frm.toggle_display("distribution_id", frm.doc.__islocal);
    }
});