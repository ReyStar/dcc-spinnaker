import sys
import datetime
import logging
from flask import Flask, request, make_response
from flask.json import jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from flask_restplus import Resource, Api, reqparse

from validation import validation_engine

app = Flask(__name__, static_url_path="")
logging.basicConfig(level=logging.DEBUG)

# uwsgi is being used only to send async jobs to the spooler.
# it's only available when the app is run in a uwsgi context.
# Allow the app to be run outside of that context for other 
# tasks, eg db migration.
# Do this after the logging is config so it we can log it.
try:
    import uwsgi
except ImportError:
    logging.info("Couldn't import uwsgi.")


@app.route("/")
def index():
    return app.send_static_file("index.html")


"""
Database and Models
"""
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////data/spinnaker.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
manager = Manager(app)
manager.add_command("db", MigrateCommand)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum("new", "received", "validated", "invalid", "signed"), default="new")
    created = db.Column(db.DateTime, default=datetime.datetime.utcnow())
    modified = db.Column(db.DateTime, default=datetime.datetime.utcnow())
    receipt = db.Column(db.Text)

    def to_dict(self):
        """ Annoyingly jsonify doesn't automatically just work... """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


"""
RESTful API
"""
api = Api(app, title="Spinnaker API", doc="/api", description="""
RESTful API for the Spinnaker submissions service

Source: https://github.com/BD2KGenomics/spinnaker
""")
app.config.SWAGGER_UI_JSONEDITOR = True

json_parser = reqparse.RequestParser()
json_parser.add_argument("json", location="json")

# test route for testing this after stuff

@api.route("/v0/submissions")
class SubmissionsAPI(Resource):

    def get(self):
        """ Get a list of all submissions """
        return jsonify(submissions=[s.to_dict() for s in Submission.query.all()])

    @api.expect(json_parser)
    def post(self):
        """ Create a new empty submission """
        fields = request.get_json()
        submission = Submission(**fields)
        db.session.add(submission)
        db.session.commit()
        logging.info("Created submission id {}".format(submission.id))
        return make_response(jsonify(submission=submission.to_dict()), 201)


@api.route("/v0/submissions/<id>")
class SubmissionAPI(Resource):

    def get(self, id):
        """ Get a submission """
        submission = Submission.query.get(id)
        if submission:
            return jsonify(submission=submission.to_dict())
        else:
            return make_response(jsonify(message="Submission {} does not exist".format(id)), 404)

    @api.expect(json_parser)
    def put(self, id):
        """ Edit a submission """
        submission = Submission.query.get(id)
        if submission:
            receipt = request.get_json().get("receipt", submission.receipt)
            submission.receipt = receipt
            submission.status = "received"
            submission.modified = datetime.datetime.utcnow()
            db.session.commit()
            logging.info("Edited submission {}".format(id))
            # Asynchronously kick off the validate if available
            if 'uwsgi' in sys.modules:
                uwsgi.spool({'key': receipt})
            else:
                logging.debug("UWSGI not available; skipping validation.")
            return jsonify(submission=submission.to_dict())
        else:
            return make_response(jsonify(message="Submission {} does not exist".format(id)), 404)

    def delete(self, id):
        """ Delete a submission """
        submission = Submission.query.get(id)
        if submission:
            db.session.delete(submission)
            db.session.commit()
            logging.info("Deleted submission {}".format(id))
            return jsonify(message="Deleted submission {}".format(id))
        else:
            return make_response(jsonify(message="Submission {} does not exist".format(id)), 404)


"""
Validation Engine
"""

@app.route("/v0/testspooler/<blah>")
def foo(blah):
    print blah
    logging.info("about to return in foo")
    if 'uwsgi' in sys.modules:
        uwsgi.spool({'key': blah})
    else:
        logging.info("UWSGI not available; skipping!")
    return "<b>yep</b> it ran"


# Run some testing validations
# TODO ultimately this will most likely not be a route
@app.route("/v0/validate/<submission_id>")
def validate(submission_id):
    submission = Submission.query.get(submission_id)
    if submission:
        receipt = submission.receipt
    else:
        return make_response(jsonify(
            message="Submission {} does not exist".format(submission_id)), 404)

    # Run the validation
    validation_result = validation_engine.validate(receipt)

    if(validation_result.validated):
        submission.status = "validated"
        submission.modified = datetime.datetime.utcnow()
        db.session.commit()
        logging.info("Validated submission {}".format(submission_id))
        message = "Validated {}".format(validation_result.response)
    else:
        submission.status = "invalid"
        submission.modified = datetime.datetime.utcnow()
        db.session.commit()
        logging.info("Invalid submission {}".format(submission_id))
        message = "Failed validation: {}".format(validation_result.response)
    return make_response(jsonify(message=message, validated=validation_result.validated), 200)


if __name__ == "__main__":
    manager.run()
