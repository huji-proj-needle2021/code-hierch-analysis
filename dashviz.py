from viz.app import app
from viz.layout import layout
import logging

app.layout = layout

if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger("graph_import").setLevel(logging.INFO)
    app.run_server(debug=True)
