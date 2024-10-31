from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///snippets.db'
db = SQLAlchemy(app)

# Define the Snippet model
class Snippet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50))
    tags = db.Column(db.String(200))  # Store tags as comma-separated string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Create a new snippet
@app.route('/api/snippets', methods=['POST'])
def create_snippet():
    data = request.get_json()
    
    # Convert tags list to comma-separated string
    tags = ','.join(data.get('tags', []))
    
    new_snippet = Snippet(
        title=data['title'],
        code=data['code'],
        language=data.get('language', ''),
        tags=tags
    )
    
    db.session.add(new_snippet)
    db.session.commit()
    
    return jsonify({
        'id': new_snippet.id,
        'title': new_snippet.title,
        'message': 'Snippet created successfully'
    }), 201

# Get all snippets
@app.route('/api/snippets', methods=['GET'])
def get_snippets():
    # Get query parameters for filtering
    language = request.args.get('language')
    tag = request.args.get('tag')
    
    query = Snippet.query
    
    if language:
        query = query.filter_by(language=language)
    if tag:
        query = query.filter(Snippet.tags.contains(tag))
    
    snippets = query.all()
    
    return jsonify([{
        'id': s.id,
        'title': s.title,
        'code': s.code,
        'language': s.language,
        'tags': s.tags.split(',') if s.tags else [],
        'created_at': s.created_at.isoformat()
    } for s in snippets])

# Get a specific snippet
@app.route('/api/snippets/<int:snippet_id>', methods=['GET'])
def get_snippet(snippet_id):
    snippet = Snippet.query.get_or_404(snippet_id)
    
    return jsonify({
        'id': snippet.id,
        'title': snippet.title,
        'code': snippet.code,
        'language': snippet.language,
        'tags': snippet.tags.split(',') if snippet.tags else [],
        'created_at': snippet.created_at.isoformat()
    })

# Update a snippet
@app.route('/api/snippets/<int:snippet_id>', methods=['PUT'])
def update_snippet(snippet_id):
    snippet = Snippet.query.get_or_404(snippet_id)
    data = request.get_json()
    
    snippet.title = data.get('title', snippet.title)
    snippet.code = data.get('code', snippet.code)
    snippet.language = data.get('language', snippet.language)
    
    if 'tags' in data:
        snippet.tags = ','.join(data['tags'])
    
    db.session.commit()
    
    return jsonify({'message': 'Snippet updated successfully'})

# Delete a snippet
@app.route('/api/snippets/<int:snippet_id>', methods=['DELETE'])
def delete_snippet(snippet_id):
    snippet = Snippet.query.get_or_404(snippet_id)
    
    db.session.delete(snippet)
    db.session.commit()
    
    return jsonify({'message': 'Snippet deleted successfully'})

if __name__ == '__main__':
    app.run(debug=True)
