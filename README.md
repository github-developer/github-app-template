⚠️ Note: This repository is not maintained. For more recent guides about how to build GitHub Apps, see "[About writing code for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/writing-code-for-a-github-app/about-writing-code-for-a-github-app)."

You can use this GitHub App template code as a foundation to create any GitHub App you'd like. You can learn how to configure a template GitHub App by following the archived "[Setting up your development environment](https://web.archive.org/web/20230604175646/https://docs.github.com/en/apps/creating-github-apps/writing-code-for-a-github-app/setting-up-your-development-environment-to-create-a-github-app)" guide.

## Install

To run the code, make sure you have [Bundler](http://gembundler.com/) installed; then enter `bundle install` on the command line.

## Set environment variables

1. Create a copy of the `.env-example` file called `.env`.
2. Add your GitHub App's private key, app ID, and webhook secret to the `.env` file.

## Run the server

1. Run `ruby template_server.rb` on the command line.
1. View the default Sinatra app at `localhost:3000`.
