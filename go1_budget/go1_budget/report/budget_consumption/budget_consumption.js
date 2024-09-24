// Copyright (c) 2024, info@tridotstech.com and contributors
// For license information, please see license.txt
/* eslint-disable */

// frappe.query_reports["Budget Consumption"] = {
// 	"filters": [

// 	]
// };

frappe.query_reports["Budget Consumption"] = {
	"filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
           
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            
        },
        {
            "fieldname": "cost_center",
            "label": __("Cost Center"),
            "fieldtype": "Link",
            "options": "Cost Center"
        },
        {
            "fieldname": "account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "Account"
        },
        {
            "fieldname": "mandate",
            "label": __("Mandate"),
            "fieldtype": "Link",
            "options": "Mandate"
        },
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "Project"
        }
    ],
};
frappe.query_reports["Budget Consumption"] = {
    "formatter": function(value, row, column, data, default_formatter) {
        var formatted_value = default_formatter(value, row, column, data);
        if ( data.indent === 0) {
            formatted_value = `<span style="font-weight:bold;">${formatted_value}</span>`;
        }

        return formatted_value;
    }
};
// frappe.query_reports["Budget Consumption"] = {
//     onload: function(report) {
//         // Wait until the report is fully loaded
//         frappe.after_ajax(function() {
//             let report_data = report.get_data();

//             // Iterate through the rows and apply bold styling directly to the cost center rows
//             report_data.forEach(row => {
//                 if (row.indent === 0) {  // For cost center rows
//                     $(`.grid-row[data-row-index="${row.idx}"]`).css("font-weight", "bold");
//                 }
//             });
//         });
//     }
// };
