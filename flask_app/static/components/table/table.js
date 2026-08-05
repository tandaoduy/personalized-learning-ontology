(function () {
    function createTable({ columns = [], rows = [], emptyText = "Không có dữ liệu" } = {}) {
        const wrap = document.createElement("div");
        wrap.className = "ui-table-wrap";

        const scroll = document.createElement("div");
        scroll.className = "ui-table-scroll";

        const table = document.createElement("table");
        table.className = "ui-table";

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        columns.forEach((column) => {
            const th = document.createElement("th");
            th.textContent = column.label || column.key || "";
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        const tbody = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            columns.forEach((column) => {
                const td = document.createElement("td");
                const value = typeof column.render === "function"
                    ? column.render(row)
                    : row[column.key];

                if (value instanceof Node) {
                    td.appendChild(value);
                } else {
                    td.textContent = value ?? "";
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        table.append(thead, tbody);
        scroll.appendChild(table);
        wrap.appendChild(scroll);

        if (!rows.length) {
            const empty = document.createElement("div");
            empty.className = "ui-table__empty";
            empty.textContent = emptyText;
            wrap.appendChild(empty);
        }

        return wrap;
    }

    window.UIComponents = window.UIComponents || {};
    window.UIComponents.createTable = createTable;
})();
