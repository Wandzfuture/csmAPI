from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime as dt
from functools import wraps


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///snippets.db'
app.config['SECRET_KEY'] = 'your-secret-key'
db = SQLAlchemy(app)


class ValidationError(Exception):
    pass


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    snippets = db.relationship('Snippet', backref='author', lazy=True)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    snippets = db.relationship('Snippet', backref='category', lazy=True)


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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

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


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            token = token.split(' ')[1]  # Remove 'Bearer ' prefix
            data = jwt.decode(
                token,
                app.config['SECRET_KEY'],
                algorithms=["HS256"]
            )
            current_user = User.query.get(data['user_id'])
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400

    hashed_password = generate_password_hash(data['password'])

    new_user = User(
        username=data['username'],
        email=data['email'],
        password=hashed_password
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    user = User.query.filter_by(username=data['username']).first()

    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + dt.timedelta(hours=24)
    }, app.config['SECRET_KEY'])

    return jsonify({'token': token})


@app.route('/api/categories', methods=['GET'])
@token_required
def get_categories(current_user):
    categories = Category.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'description': c.description
    } for c in categories])


@app.route('/api/categories', methods=['POST'])
@token_required
def create_category(current_user):
    data = request.get_json()

    new_category = Category(
        name=data['name'],
        description=data.get('description', '')
    )

    db.session.add(new_category)
    db.session.commit()

    return jsonify({'message': 'Category created successfully'}), 201


@app.route('/api/snippets', methods=['POST'])
@token_required
def create_snippet(current_user):
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("No data provided")

        tags = ','.join(data.get('tags', []))

        new_snippet = Snippet(
            title=data.get('title', '').strip(),
            code=data.get('code', '').strip(),
            language=data.get('language', '').strip(),
            tags=tags,
            user_id=current_user.id,
            category_id=data.get('category_id')
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
@token_required
def get_snippets(current_user):
    try:
        language = request.args.get('language')
        tag = request.args.get('tag')
        search = request.args.get('search')
        category_id = request.args.get('category_id')

        query = Snippet.query.filter_by(user_id=current_user.id)

        if language:
            query = query.filter_by(language=language)
        if tag:
            query = query.filter(Snippet.tags.contains(tag))
        if search:
            search_term = f"%{search}%"
            query = query.filter(or_(
                Snippet.title.ilike(search_term),
                Snippet.code.ilike(search_term)
            ))
        if category_id:
            query = query.filter_by(category_id=category_id)

        snippets = query.all()

        return jsonify([{
            'id': s.id,
            'title': s.title,
            'code': s.code,
            'language': s.language,
            'tags': s.tags.split(',') if s.tags else [],
            'created_at': s.created_at.isoformat(),
            'last_updated': s.last_updated.isoformat(),
            'category_id': s.category_id
        } for s in snippets])

    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve snippets',
            'details': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
