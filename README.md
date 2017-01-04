[![Build Status](https://travis-ci.org/BD2KGenomics/dcc-spinnaker.svg?branch=master)](https://travis-ci.org/BD2KGenomics/dcc-spinnaker)

# Spinnaker Server
Receives receipts from the spinnaker upload client and validates the submissions

# Run

Start the database container:

    make db

Run the spinnaker server in a container:

    make run

NOTE: make run will also create and migrate the database if required

# Build, Debug and Test Locally

Start the database container:

    make db

Create the database if it doens't exist and apply any migrations:

    make upgrade

Build a local spinnaker docker container:

    make build

Run a debug server

    make debug

This runs the spinnaker container listening on port 5000 out of the local folder so
you can make changes and it will live reload.

To run tests open another terminal window and:

    make test

# Database Migrations

After making changes to the model:

    make migrate

which will create a new migration in /migrations which will get applied via make upgrade

# API

To view the swagger REST API documentation open a browser to <server>/api
