// Se establece el requerimiento de las dependencias
var express = require('express');
var bodyParser = require('body-parser');
  
// Se instancia el módulo de express
var app = express();
  
// Se establece el uso de un parseo para e cuerpo de los mensajes recibidos
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: false }));
app.use(express.static("public"))
 // Se define la variable que guardará la metadata recibida
var metadata = {}

// Se define la función que obtendrá los datos de python
app.post("/status", (req, res) => {
  
    metadata = req.body
    res.json({ result: 'done' });
    
});


app.get("/taqueria", (req, res) => {
    res.json(metadata)
})

// Establecemos el puerto a escuchar
app.listen(3001);
