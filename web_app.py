import flask
from ysa_shell import YSAShell

shell = YSAShell()
app = flask.Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

@app.route('/api/message', methods=['POST'])
def new_message():
    abort = not flask.request.json \
        or not 'person' in flask.request.json \
        or not 'type' in flask.request.json \
        or not 'text' in flask.request.json
    if abort:
        flask.abort(400)
    task = {
        'id': tasks[-1]['id'] + 1,
        'title': request.json['title'],
        'description': request.json.get('description', ""),
        'done': False
    }
    tasks.append(task)
    return flask.jsonify({'task': task}), 201

if __name__ == '__main__':
    app.run(debug=True)