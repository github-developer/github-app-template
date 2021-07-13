# Physical power consumption tester meant to run as continuous integration. 

Runs as a "Github app" alongside the CircleCI Github App 

Only triggers on repositories named "dialog_14683_scratch" 

Secrets (i.e. API keys) must be added in ".env" file. Example provided in ".env-example"

Needs to run on Windows because the script to flash the P7 is "initial_flash.bat". Path to dialog_14683_scratch repository must be specified in `reprogram_p7.sh`

High level overview of program flow: 

"diagram here"

Created from Github App Template: 
You can use this GitHub App template code as a foundation to create any GitHub App you'd like. You can learn how to configure a template GitHub App by following the "[Setting up your development environment](https://developer.github.com/apps/quickstart-guides/setting-up-your-development-environment/)" quickstart guide on developer.github.com.

## Install

To run the code, make sure you have [Bundler](http://gembundler.com/) installed; then enter `bundle install` on the command line.

## Set environment variables

1. Create a copy of the `.env-example` file called `.env`.
2. Add your GitHub App's private key, app ID, and webhook secret to the `.env` file.

## Run the server

1. Run `ruby template_server.rb` on the command line.
1. View the default Sinatra app at `localhost:3000`.
