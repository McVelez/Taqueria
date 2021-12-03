# Taqueria
<div>
<p style="text-align: center;">El problema presentado plantea la representación de 4 taqueros que se encargan de realizar tacos de asada, adobada, lengua, cabeza y suadero (dos taqueros se encargan de realizar asada y suadero, uno se encarga de tripa y cabeza y otro se encarga de los tacos de adobada), un quesadillero, 2 chalanes, un set de fillings y un set de tortillas (que no poseen un límite establecido) los cuales mantienen ciertas relaciones para la resolución de un objetivo (ejemplo, el chalán se encuentra relacionado con aquellos fillings anteriormente mencionados, los cuales permiten que el taquero los agregue a cada taco dependiendo de las especificaciones de determinada orden). 
</p>

<p>En base a lo identificado anteriormente es necesario mantener un conjunto de estructuras, en donde se identifican tres puntos de enfoque: los taqueros que comparten un queue, el quesadillero y los taqueros individuales.</p>

<p>Por otro lado, es necesario mantener una recolección de todas las órdenes que están siendo procesadas en determinada instancia de tiempo por cualquiera de los taqueros antes descritos y todas las órdenes finalizadas, manteniendo así un recopilación de detalles de cada orden: identificador, las subórdenes que componen a dicha orden, fecha y su estatus.
Identificamos la importancia de delimitar lo que se considera como una orden grande y pequeña puesto que nos permitirá categorizar e identificar las prioridades que le hemos asignado a cada una de ellas y por lo tanto, la forma en que los procesos se adecuan a ellas.</p>
</div>
<div>
<ul>
    <li>**Dependencias necesarias por instalar para la taquería**</li>
    <ul>
        <li> boto3 (1.18.48) - para instalar: pip install boto3 </li>
        <li> requests (2.25.0) - para instalar: pip install requests </li>
    </ul>
    <li> **Dependencias necesarias por instalar para el visualizador**</li>
    <ul>
        <li>node (14.4) - node https://nodejs.org/en/ </li>
        <li>body-parser (1.19.0) - para instalar: npm install body-parser</li>
        <li>express (4.17.1) - para instalar: npm install nodemon</li>
        <li>nodemon (2.0.15) - para instalar: npm install nodemon</li>
    </ul>
    <li> El archivo de _Taqueria_Main.py_ es el archivo principal utiliado para ejecutar/poner en función la taquería. (Siempre y cuando el SQS del cual se obtienen las subórdenes contenga mensajes) </li>
    <li> El resultado generado de la taquería es un archivo llamado _response.json_ que constantemente es actualizado conforme se van realizando acciones y cambios de valores a las órdenes leídas del SQS. </li>
    <li> El visualizador se encuentra en la carpeta homónima, puara hacer uso de él solamente es necesario abrir dicha carpeta en la terminal y ejectur lo siguiente: _npm run dev_, después de lo cual solo es necesario dirigirse al siguiente url en el navegador: _ http://localhost:3001/ _ </li>
</ul>
</div>

