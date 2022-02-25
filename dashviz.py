from viz import app
import logging


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger("graph_import").setLevel(logging.INFO)
    app.run_server(debug=True)
