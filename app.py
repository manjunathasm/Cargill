import os
import yaml
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from apispec.utils import validate_spec
from marshmallow import Schema, fields
from flask_cors import CORS
from functools import wraps
from flask import (
    jsonify,
    request,
)

app = Flask(__name__, template_folder='swagger/templates')
CORS(app)

app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

OPENAPI_SPEC = """
openapi: 3.0.3
info:
  description: Cargill Server API Swagger document
  title: Cargill Server API
  version: 1.0.0
servers:
- url: http://127.0.0.1:5000/
  description: The development API server
  variables:
    port:
      enum:
      - '5000'
      default: '5000'
"""

settings = yaml.safe_load(OPENAPI_SPEC)
# retrieve  title, version, and openapi version
title = settings["info"].pop("title")
spec_version = settings["info"].pop("version")
openapi_version = settings.pop("openapi")


spec = APISpec(
    title=title,
    version=spec_version,
    openapi_version=openapi_version,
    plugins=[FlaskPlugin(), MarshmallowPlugin()],
    ** settings
)

validate_spec(spec)


@app.route("/")
def hello():
    return "Hello Cargill"


@app.route('/api/swagger.json')
def create_swagger_spec():
    return jsonify(spec.to_dict())


team_role = db.Table('team_role',
                     db.Column('team_id', db.Integer,
                               db.ForeignKey('teams.id')),
                     db.Column('role_id', db.Integer,
                               db.ForeignKey('roles.id'))
                     )


class AssignTeamRoleSchema(Schema):
    team_name = fields.String()
    role_name = fields.String()


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    roles = db.relationship('Role', secondary=team_role, backref='teams')

    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        return '{}'.format(self.name)

    def get_roles(self):
        if self.roles:
            return [role.name for role in self.roles]
        return []

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }


class TeamParam(Schema):
    team_id = fields.Int()


class TeamSchema(Schema):
    id = fields.Int()
    name = fields.String()
    description = fields.String()
    roles = fields.List(fields.String())


class TeamCreateSchema(Schema):
    name = fields.String()
    description = fields.String()


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)

    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        return '{}'.format(self.name)

    def get_teams(self):
        if self.teams:
            return [team.name for team in self.teams]
        return []

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }


class RoleParam(Schema):
    role_id = fields.Int()


class RoleSchema(Schema):
    id = fields.Int()
    name = fields.String()
    description = fields.String()
    teams = fields.List(fields.String())


class RoleCreateSchema(Schema):
    name = fields.String()
    description = fields.String()


class GetTeamRolesParam(Schema):
    team_name = fields.String()


@app.route('/team/<team_id>', methods=['GET'])
def get_team(team_id):
    """Get Team
    ---
    get:
        tags:
        - Team
        summary: Get Team by id
        description: Get Team by id
        parameters:
        -   in: path
            schema: TeamParam
        responses:
            200:
                description: Return a team
                content:
                    application/json:
                        schema: TeamSchema
            404:
                description: Team id {team_id} not found
    """

    content_type = {'ContentType': 'application/json'}

    team = Team.query.get(team_id)
    if team:
        result = team.serialize()
        return {"success": True, "data": result}, 200, content_type
    else:
        return {"success": False, "message": f"Team id {team_id} not found"}, 404, content_type


@app.route('/teams', methods=['GET'])
def get_teams():
    """Get Teams
    ---
    get:
        tags:
        - Team
        summary: Get List of Teams
        description: Get List of Teams
        responses:
            200:
                description: Return a team list
                content:
                    application/json:
                        schema: TeamSchema
    """

    content_type = {'ContentType': 'application/json'}

    teams = Team.query.all()
    results = [team.serialize() for team in teams]

    return {"Success": True, "count": len(results), "data": results}, 200, content_type


@app.route('/teams', methods=['POST'])
def create_team():
    """Create Team
    ---
    post:
        tags:
        - Team
        summary: Create new Team
        description: create new Team
        requestBody:
            required: true
            content:
                application/json:
                    schema: TeamCreateSchema
        responses:
            200:
                description: Return a response object
                content:
                    application/json:
                        Model:
                            type: object
                            properties:
                                data: TeamSchema
            400:
                description: Missing request payload
            409:
                description: Team already exists
    """

    content_type = {'ContentType': 'application/json'}

    try:
        if request.is_json:
            data = request.get_json()
            new_team = Team(
                name=data['name'], description=data['description'])
            db.session.add(new_team)
            db.session.commit()
            return {'success': True, "message": f"Team {new_team.name} has been created successfully"}, 200, content_type
        else:
            return {"success": False, "message": "The request payload is not in JSON format"}, 400, content_type
    except Exception:
        return {"success": False, "message": f"Team {data['name']} already exists"}, 409, content_type


@app.route('/team/<team_id>', methods=['DELETE'])
def delete_team(team_id):
    """Delete Team
    ---
    delete:
        tags:
        - Team
        summary: Delete Team by id
        description: Delete Team by id
        parameters:
        -   in: path
            schema: TeamParam
        responses:
            200:
                description: Team id {team_id} Deleted success
            404:
                description: Team id {team_id} not found
    """

    content_type = {'ContentType': 'application/json'}

    team = Team.query.get(team_id)
    if team:
        db.session.delete(team)
        db.session.commit()
        return {"success": True, "message": f"Team {team_id} Deleted success"}, 200, content_type
    else:
        return {"success": False, "message": f"Team id {team_id} not found"}, 404, content_type


@app.route('/role/<role_id>', methods=['GET'])
def get_role(role_id):
    """Get Role
    ---
    get:
        tags:
        - Role
        summary: Get Role by id
        description: Get Role by id
        parameters:
        -   in: path
            schema: RoleParam
        responses:
            200:
                description: Return a role
                content:
                    application/json:
                        schema: RoleSchema
            404:
                description: Role id {role_id} not found
    """

    content_type = {'ContentType': 'application/json'}

    role = Role.query.get(role_id)
    if role:
        result = role.serialize()
        return {"success": True, "data": result}, 200, content_type
    else:
        return {"success": False, "message": f"Role id {role_id} not found"}, 404, content_type


@app.route('/roles', methods=['GET'])
def get_roles():
    """Get Roles
    ---
    get:
        tags:
        - Role
        summary: Get List of Roles
        description: Get List of Roles
        responses:
            200:
                description: Return a role list
                content:
                    application/json:
                        schema: RoleSchema
    """

    content_type = {'ContentType': 'application/json'}

    roles = Role.query.all()
    results = [role.serialize() for role in roles]

    return {"success": True, "count": len(results), "data": results}, 200, content_type


@app.route('/roles', methods=['POST'])
def create_role():
    """Create Role
    ---
    post:
        tags:
        - Role
        summary: Create new Role
        description: Create new Role
        requestBody:
            required: true
            content:
                application/json:
                    schema: RoleCreateSchema
        responses:
            200:
                description: Return a response object
                content:
                    application/json:
                        Model:
                            type: object
                            properties:
                                data: RoleSchema
            400:
                description: Missing request payload
            409:
                description: Role already exists
    """

    content_type = {'ContentType': 'application/json'}

    try:
        if request.is_json:
            data = request.get_json()
            new_role = Role(
                name=data['name'], description=data['description'])
            db.session.add(new_role)
            db.session.commit()
            return {"success": True, "message": f"Role {new_role.name} has been created successfully"}, 200, content_type
        else:
            return {"success": False, "message": "The request payload is not in JSON format"}, 400, content_type
    except Exception:
        return {"success": False, "message": f"Role {data['name']} already exists"}, 409, content_type


@app.route('/role/<role_id>', methods=['DELETE'])
def delete_role(role_id):
    """Delete Role
    ---
    delete:
        tags:
        - Role
        summary: Delete Role by id
        description: Delete Role by id
        parameters:
        -   in: path
            schema: RoleParam
        responses:
            200:
                description: Role id {role_id} Deleted success
            404:
                description: Role id {role_id} not found
    """

    content_type = {'ContentType': 'application/json'}

    role = Role.query.get(role_id)
    if role:
        db.session.delete(role)
        db.session.commit()
        return {"success": True, "message": f"Role id {role_id} Deleted success"}, 200, content_type
    else:
        return {"success": False, "message": f"Role id {role_id} not found"}, 404, content_type


def validate_json(f):
    @wraps(f)
    def wrapper(*args, **kw):
        try:
            request.json
        except BadRequest as e:
            msg = "payload must be a valid json"
            return jsonify({"error": msg}), 400
        return f(*args, **kw)
    return wrapper


@app.route('/team/assign/role', methods=['POST'])
@validate_json
def assign_role():
    """Assign Role
    ---
    post:
        tags:
        - Team Role
        summary: Assign new Role
        description: Assign new Role
        requestBody:
            required: true
            content:
                application/json:
                    schema: AssignTeamRoleSchema
        responses:
            200:
                description: Return a Response Object
            400:
                description: Missing request payload
            404:
                description: Team/Role not found
    """

    content_type = {'ContentType': 'application/json'}

    if request.is_json:
        data = request.get_json()
        team_name = data["team_name"]
        role_name = data["role_name"]

        team = Team.query.filter(Team.name == team_name).first()
        role = Role.query.filter(Role.name == role_name).first()

        if not team:
            return {"success": False, "message": f"Team {team_name} does not exist"}, 404, content_type
        if not role:
            return {"success": False, "message": f"Role {role_name} does not exist"}, 404, content_type

        team.roles.append(role)

        db.session.commit()

        return {"success": True, "message": f"Assign Role {role_name} to Team {team_name} is success"}, 200, content_type
    else:
        return {"success": False, "message": "The request payload is not in JSON format"}, 400, content_type


@app.route('/team/<team_name>/roles', methods=['GET'])
def get_team_roles(team_name):
    """Get Team Roles 
    ---
    get:
        tags:
        - Team Role
        summary: Get Roles by Team name
        description: Get Roles by Team name
        parameters:
        -   in: path
            schema: GetTeamRolesParam
        responses:
            200:
                description: Return a Roles names list
            404:
                description: Team id {team_name} not found
    """

    content_type = {'ContentType': 'application/json'}

    team = Team.query.filter(Team.name == team_name).first()
    if team:
        result = team.get_roles()
        return {"success": True, "data": result}, 200, content_type
    else:
        return {"success": False, "message": f"Team {team_name} not found"}, 404, content_type


with app.test_request_context():
    spec.path(view=get_team)
    spec.path(view=get_teams)
    spec.path(view=create_team)
    spec.path(view=delete_team)
    spec.path(view=get_role)
    spec.path(view=get_roles)
    spec.path(view=create_role)
    spec.path(view=delete_role)
    spec.path(view=assign_role)
    spec.path(view=get_team_roles)


@app.route('/docs')
@app.route('/docs/<path:path>')
def swagger_docs(path=None):
    if not path or path == 'index.html':
        return render_template('index.html', base_url='/docs')
    else:
        return send_from_directory('./swagger/static', secure_filename(path))


if __name__ == '__main__':
    app.run()
