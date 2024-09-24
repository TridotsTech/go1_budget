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
    }
});