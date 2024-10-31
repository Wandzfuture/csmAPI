from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import or_


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///snippets.db'
db = SQLAlchemy(app)


class ValidationError(Exception):
    pass


class Snippet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50))
    tags = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def validate(self):
        if not self.title or len(self.title.strip()) == 0:
            raise ValidationError("Title cannot be empty")
        if not self.code or len(self.code.strip()) == 0:
            raise ValidationError("Code cannot be empty")
        if len(self.title) > 100:
            raise ValidationError("Title must be less than 100 characters")
        if self.language and len(self.language) > 50:
            raise ValidationError("Language must be less than 50 characters")


# Create tables
with app.app_context():
    db.create_all()


@app.errorhandler(ValidationError)
def handle_validation_error(error):
    return jsonify({'error': str(error)}), 400


@app.errorhandler(Exception)
def handle_general_error(error):
    return jsonify({
        'error': 'An unexpected error occurred',
        'details': str(error)
    }), 500


@app.route('/api/snippets', methods=['POST'])
def create_snippet():
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("No data provided")

        # Convert tags list to comma-separated string
        tags = ','.join(data.get('tags', []))

        new_snippet = Snippet(
            title=data.get('title', '').strip(),
            code=data.get('code', '').strip(),
            language=data.get('language', '').strip(),
            tags=tags
        )

        new_snippet.validate()

        db.session.add(new_snippet)
        db.session.commit()

        return jsonify({
            'id': new_snippet.id,
            'title': new_snippet.title,
            'message': 'Snippet created successfully'
        }), 201

    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({
            'error': 'Failed to create snippet',
            'details': str(e)
        }), 500


@app.route('/api/snippets', methods=['GET'])
def get_snippets():
    try:
        # Get query parameters for filtering and search
        language = request.args.get('language')
        tag = request.args.get('tag')
        search = request.args.get('search')  # New search parameter

        query = Snippet.query

        # Apply filters
        if language:
            query = query.filter_by(language=language)
        if tag:
            query = query.filter(Snippet.tags.contains(tag))
        if search:
            # Search in title and code
            search_term = f"%{search}%"
            query = query.filter(or_(
                Snippet.title.ilike(search_term),
                Snippet.code.ilike(search_term)
            ))

        snippets = query.all()

        return jsonify([{
            'id': s.id,
            'title': s.title,
            'code': s.code,
            'language': s.language,
            'tags': s.tags.split(',') if s.tags else [],
            'created_at': s.created_at.isoformat(),
            'last_updated': s.last_updated.isoformat()
        } for s in snippets])

    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve snippets',
            'details': str(e)
        }), 500


@app.route('/api/snippets/<int:snippet_id>', methods=['GET'])
def get_snippet(snippet_id):
    try:
        snippet = Snippet.query.get_or_404(snippet_id)

        return jsonify({
            'id': snippet.id,
            'title': snippet.title,
            'code': snippet.code,
            'language': snippet.language,
            'tags': snippet.tags.split(',') if snippet.tags else [],
            'created_at': snippet.created_at.isoformat(),
            'last_updated': snippet.last_updated.isoformat()
        })

    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve snippet',
            'details': str(e)
        }), 500


@app.route('/api/snippets/<int:snippet_id>', methods=['PUT'])
def update_snippet(snippet_id):
    try:
        snippet = Snippet.query.get_or_404(snippet_id)
        data = request.get_json()

        if not data:
            raise ValidationError("No data provided")

        if 'title' in data:
            snippet.title = data['title'].strip()
        if 'code' in data:
            snippet.code = data['code'].strip()
        if 'language' in data:
            snippet.language = data['language'].strip()
        if 'tags' in data:
            snippet.tags = ','.join(data['tags'])

        snippet.validate()
        db.session.commit()

        return jsonify({
            'message': 'Snippet updated successfully',
            'last_updated': snippet.last_updated.isoformat()
        })

    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({
            'error': 'Failed to update snippet',
            'details': str(e)
        }), 500


@app.route('/api/snippets/<int:snippet_id>', methods=['DELETE'])
def delete_snippet(snippet_id):
    try:
        snippet = Snippet.query.get_or_404(snippet_id)

        db.session.delete(snippet)
        db.session.commit()

        return jsonify({'message': 'Snippet deleted successfully'})

    except Exception as e:
        return jsonify({
            'error': 'Failed to delete snippet',
            'details': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
