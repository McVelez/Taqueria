var express = require('express');
var bodyParser = require('body-parser');
  
var app = express();
  
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: false }));
app.use(express.static("public"))

var metadata = {}

app.post("/status", (req, res) => {
  
    metadata = req.body
    res.json({ result: 'done' });
    
});


app.get("/taqueria", (req, res) => {
    res.json(metadata)
})

app.listen(3001);
