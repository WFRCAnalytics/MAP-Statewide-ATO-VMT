# MAP-Statewide-ATO-VMT
This repo brings together the ATO and VMT data from all the models in the state and creates a simple web map to view the data.

Pukar recommends the following:
 - ViteJS (dashboard framework for Javascript like Shiny is for R)
 - PMTiles
 - MapLibre

A great example of how to build the map can be found studying the Housing Site Evaluator Map (wfrc.shinyapps.io/housing-site-evaluator/). It should be the reference for the style of how the web map should look, as well as the code framework and how to create the site. A few other things to note about this repo are:
 - ignore the _app folder. This is just the relic of the older version which was hosted via R Shiny
 - reference the _site folder. This is the code for the ViteJS and will give a fantastic reference for this map.
 