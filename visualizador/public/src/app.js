
async function update(root) {
        const table = root.querySelector(".metadata_table");
        const response = await fetch(root.dataset.url);
        const dataRes = await response.json();
        const data = dataRes.taqueros
        table.querySelector("thead tr").innerHTML= "";
        table.querySelector("tbody").innerHTML = "";
        const headers = ['Name', "Tacos", "Salsa", "Guacamole", "Cebolla", "Cilantro", "Tortillas", "Stack", "Fan", "Rest"];

        for (const h of headers){
            table.querySelector("thead tr").insertAdjacentHTML("beforeend", `<th> ${ h } </th>`);
        }
        
        for (const row in data){
            table.querySelector("tbody").insertAdjacentHTML("beforeend",`
                <tr>
                    ${ data[row].map(col => `<td class="cell" v = ${ col } > ${ col } </td>`).join("") }
                </tr>
            `);
        }
    }

async function updateTacos(root){
    const tableTacos = root.querySelector(".tacos_table_");
    const response = await fetch(root.dataset.url);
    const dataRes = await response.json();
    const data = dataRes.orders;
    console.log(data)
    tableTacos.querySelector("thead tr").innerHTML= "";
    tableTacos.querySelector("tbody").innerHTML = "";
    const headersTacos = ['Part id', "Type", "Meat", "Remaining Tacos"];
    
    for (const h_ of headersTacos){
        tableTacos.querySelector("thead tr").insertAdjacentHTML("beforeend", `<th> ${ h_ } </th>`);
    }
    for (const row in data){

        tableTacos.querySelector("tbody").insertAdjacentHTML("beforeend",`
            <tr>
                ${ data[row].map(col => `<td> ${ col } </td>`).join("") }
            </tr>
        `);
    }
}

async function updateQuesadillas(root){
    const table = root.querySelector(".metadata_table_Q");
    const response = await fetch(root.dataset.url);
    const dataRes = await response.json();
    const data = dataRes.quesas;
    table.querySelector("thead tr").innerHTML= "";
    table.querySelector("tbody").innerHTML = "";
    const headers = ['Part id', "Remaining", "Queued"];
    console.log(data)
    for (const h_ of headers){
        table.querySelector("thead tr").insertAdjacentHTML("beforeend", `<th> ${ h_ } </th>`);
    }
    if (data){
        table.querySelector("tbody").insertAdjacentHTML("beforeend",`
            <tr>
                ${ data.map(col => `<td> ${ col } </td>`).join("") }
            </tr>
        `);
    }
    
}
//table-quesadillero
for (const root of document.querySelectorAll(".table-quesadillero[data-url]")){
    
    const table = document.createElement("table");
    table.classList.add("metadata_table_Q");
    table.innerHTML = `
        <thead>
            <tr></tr>
        </thead>
        <tbody>
            <tr>
                <td>Loading</td>
            </tr>
        </tbody>
    `;
    root.append(table);
    updateQuesadillas(root);
}

for (const root of document.querySelectorAll(".table-tacos[data-url]")){
    
    const table_ = document.createElement("table");
    table_.classList.add("tacos_table_");
    table_.innerHTML = `
        <thead>
            <tr></tr>
        </thead>
        <tbody>
            <tr>
                <td>Loading</td>
            </tr>
        </tbody>
    `;
    root.append(table_);
    updateTacos(root);
}

for (const root of document.querySelectorAll(".table-refresh[data-url]")){
    const table = document.createElement("table");
    table.classList.add("metadata_table");
    table.innerHTML = `
        <thead>
            <tr></tr>
        </thead>
        <tbody>
            <tr>
                <td>Loading</td>
            </tr>
        </tbody>
    `;
    root.append(table);
    update(root);
}


