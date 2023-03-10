from flask import *
# from shell import YSAShell

# shell = YSAShell()
app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

# @app.route('/api/message', methods=['POST'])
# def new_message():
#     abort = not flask.request.json \
#         or not 'person' in flask.request.json \
#         or not 'type' in flask.request.json \
#         or not 'text' in flask.request.json
#     if abort:
#         flask.abort(400)
#     task = {
#         'id': tasks[-1]['id'] + 1,
#         'title': request.json['title'],
#         'description': request.json.get('description', ""),
#         'done': False
#     }
#     tasks.append(task)
#     return flask.jsonify({'task': task}), 201

@app.route('/api', methods=['post'])
def config():
    if not request.json:
        abort(400)
    response = {"challenge": request.json["challenge"]}
    return jsonify(response)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="5000")