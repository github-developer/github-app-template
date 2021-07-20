require 'sinatra'
require 'octokit'
require 'dotenv/load' # Manages environment variables
require 'json'
require 'openssl'     # Verifies the webhook signature
require 'jwt'         # Authenticates a GitHub App
require 'time'        # Gets ISO 8601 representation of a Time object
require 'logger'      # Logs debug statements
require 'git'
require 'httparty'
require 'open3'

set :port, 3000
set :bind, '0.0.0.0'

DIALOG_WORKSPACE = "/c/hh/dialog_14683_scratch"

REPOSITORY_NAME = "dialog_14683_scratch"    #prevent running on other repositories 
MAX_RETRY_TIME_ELAPSED = 60 * 14  # wait 14 minutes maximum to download firmware after starting the check run 
    
# This is template code to create a GitHub App server.
# You can read more about GitHub Apps here: # https://developer.github.com/apps/
#
# On its own, this app does absolutely nothing, except that it can be installed.
# It's up to you to add functionality!
# You can check out one example in advanced_server.rb.
#
# This code is a Sinatra app, for two reasons:
#   1. Because the app will require a landing page for installation.
#   2. To easily handle webhook events.
#
# Of course, not all apps need to receive and process events!
# Feel free to rip out the event handling code if you don't need it.
#
# Have fun!
#

BOOTLOADER_UTILS_PATH="#{DIALOG_WORKSPACE}/utilities/scripts/qspi"
HPY_UTILS_PATH="#{DIALOG_WORKSPACE}/utilities/scripts/hpy/v11"

class GHAapp < Sinatra::Application

  # Expects that the private key in PEM format. Converts the newlines
  PRIVATE_KEY = OpenSSL::PKey::RSA.new(ENV['GITHUB_PRIVATE_KEY'].gsub('\n', "\n"))

  # Your registered app must have a secret set. The secret is used to verify
  # that webhooks are sent by GitHub.
  WEBHOOK_SECRET = ENV['GITHUB_WEBHOOK_SECRET']

  # The GitHub App's identifier (type integer) set when registering an app.
  APP_IDENTIFIER = ENV['GITHUB_APP_IDENTIFIER']

  # Turn on Sinatra's verbose logging during development
  configure :development do
    set :logging, Logger::DEBUG
  end


  # Before each request to the `/event_handler` route
  before '/event_handler' do
    get_payload_request(request)
    verify_webhook_signature
    authenticate_app
    # Authenticate the app installation in order to run API operations
    authenticate_installation(@payload)
  end


  post '/event_handler' do

    # Get the event type from the HTTP_X_GITHUB_EVENT header
    case request.env['HTTP_X_GITHUB_EVENT']
    when 'check_run'
      # Check that the event is being sent to this app
      if @payload['check_run']['app']['id'].to_s === APP_IDENTIFIER
        case @payload['action']
        when 'created'
          initiate_check_run
        when 'rerequested'
          create_check_run
        end
      end
    when 'check_suite'
      # A new check_suite has been created. Create a new check run with status queued
      if @payload['action'] == 'requested' || @payload['action'] == 'rerequested'
        create_check_run
      end
    end
  
    # # # # # # # # # # # #
    # ADD YOUR CODE HERE  #
    # # # # # # # # # # # #


    200 # success status
  end


  helpers do

    # # # # # # # # # # # # # # # # #
    # ADD YOUR HELPER METHODS HERE  #
    # # # # # # # # # # # # # # # # #
    # Start the CI process
    def initiate_check_run
      # Once the check run is created, you'll update the status of the check run
      # to 'in_progress' and run the CI process. When the CI finishes, you'll
      # update the check run status to 'completed' and add the CI results.

      if @payload['repository']['name'] != REPOSITORY_NAME
        return 
      end

      @installation_client.update_check_run(
        @payload['repository']['full_name'],
        @payload['check_run']['id'],
        status: 'queued',
        accept: 'application/vnd.github.v3+json'
      )


      result = download_firmware
      if result == "max_timeout_reached"
        # Mark the check run as timed out
        @installation_client.update_check_run(
          @payload['repository']['full_name'],
          @payload['check_run']['id'],
          status: 'completed',
          ## Conclusion: 
          #  Can be one of action_required, cancelled, failure, neutral, success, 
          #  skipped, stale, or timed_out. When the conclusion is action_required, 
          #  additional details should be provided on the site specified by details_url.
          conclusion: "timed_out", 
          output: {
            title: @payload['check_run']['name'],
            summary: "Firmware download did not finish after #{MAX_RETRY_TIME_ELAPSED}s. Did CircleCI build successfully?",
          },
          accept: 'application/vnd.github.v3+json'
        )
        return result
      end

      output = program_p7
      if output.include?("cannot open gdb interface") 
         # Mark the check run as failed
         @installation_client.update_check_run(
          @payload['repository']['full_name'],
          @payload['check_run']['id'],
          status: 'completed',
          ## Conclusion: 
          #  Can be one of action_required, cancelled, failure, neutral, success, 
          #  skipped, stale, or timed_out. When the conclusion is action_required, 
          #  additional details should be provided on the site specified by details_url.
          conclusion: "cancelled", 
          output: {
            title: @payload['check_run']['name'],
            summary: "cannot open gdb interface. A cable is disconnected or the power is off",
          },
          accept: 'application/vnd.github.v3+json'
        )

        return "program_p7_failed"
      elsif output.include?("done.") == false
        # Mark the check run as failed
        @installation_client.update_check_run(
          @payload['repository']['full_name'],
          @payload['check_run']['id'],
          status: 'completed',
          ## Conclusion: 
          #  Can be one of action_required, cancelled, failure, neutral, success, 
          #  skipped, stale, or timed_out. When the conclusion is action_required, 
          #  additional details should be provided on the site specified by details_url.
          conclusion: "cancelled", 
          output: {
            title: @payload['check_run']['name'],
            summary: "Unknown error. Details below",
            text: output
          },
          accept: 'application/vnd.github.v3+json'
        )

        return "program_p7_failed"
      end

      result = joulescope_measurement
      # Turn on Joulescope and start measuring 
      
      # ***** RUN A CI TEST *****
      full_repo_name = @payload['repository']['full_name']
      repository     = @payload['repository']['name']
      head_sha       = @payload['check_run']['head_sha']




      # Run RuboCop on all files in the repository
      clone_repository(full_repo_name, repository, head_sha)
      `rm -rf #{repository}`

      # Updated check run summary and text parameters
      text = "None"
      ## ****** END CI TEST *****

      # Mark the check run as complete! And if there are warnings, share them.
      @installation_client.update_check_run(
        @payload['repository']['full_name'],
        @payload['check_run']['id'],
        status: 'completed',
        ## Conclusion: 
        #  Can be one of action_required, cancelled, failure, neutral, success, 
        #  skipped, stale, or timed_out. When the conclusion is action_required, 
        #  additional details should be provided on the site specified by details_url.
        conclusion: "neutral", 
        output: {
          title: @payload['check_run']['name'],
          summary: "image here **markdown test** <i>Italics test</i>",
          text: result,
        },
        accept: 'application/vnd.github.v3+json'
      )
    end

    RETRY_PERIOD = 15  # seconds
      
    #### Download the pre-built firmware from the blessed source: CircleCI ####
    def download_firmware
      retry_time_elapsed = 0 
      # Fetch the CircleCI job that contains the firmware. There should only be one match. 
      begin 
        begin 
          response = HTTParty.get('https://circleci.com/api/v1.1/project/github/happy-health/dialog_14683_scratch?limit=40&offset=0', :headers => {"Circle-Token" => ENV['CIRCLE_CI_API_TOKEN']})
          
          if response.code == 404 
            raise "HTTP Response 404. Check CircleCI API key"  
          end
          if response.code != 200
            raise "HTTP Response #{response.code}"
          end
        rescue RuntimeError => e
          if retry_time_elapsed > MAX_RETRY_TIME_ELAPSED
            logger.debug "Error: max timeout reached." 
            return "max_timeout_reached"
          end 
          logger.debug "Error: #{e}, retrying in #{RETRY_PERIOD} seconds..."
          retry_time_elapsed = retry_time_elapsed + RETRY_PERIOD
          sleep(RETRY_PERIOD)
          retry
        end

        response_parsed = JSON.parse(response)
        # Filter for "vcs_revision" == commit hash  and "build_parameters"["CIRCLE_JOB"] == "pack_images"
        circleCI_jobs = response_parsed.select{|job| job["vcs_revision"] == @payload['check_run']['head_sha'] && job["build_parameters"]["CIRCLE_JOB"] == "pack_images"}
        if circleCI_jobs.length() == 0
          raise "CircleCI pack_images job not created yet. Commit " + @payload['check_run']['head_sha'][0..6]
        else  
          # Check if job is finished yet 
          if circleCI_jobs[0]["status"] == "failed" || circleCI_jobs[0]["status"] == "cancelled" || circleCI_jobs[0]["status"] == "blocked" 
            raise "pack_images job failed-blocked-cancelled"
            return "pack_images job failed-blocked-cancelled"
          elsif circleCI_jobs[0]["status"] != "success"
            raise "pack_images job status: " + circleCI_jobs[0]["status"]
          end
          # else job is a success 
          logger.debug "CircleCI \"pack_images\" job found for commit " + @payload['check_run']['head_sha'] 
        end
      rescue RuntimeError => e
        if retry_time_elapsed > MAX_RETRY_TIME_ELAPSED
          logger.debug "Error: max timeout reached." 
          return "max_timeout_reached"
        end 
        logger.debug "Error: #{e}, retrying in #{RETRY_PERIOD} seconds..."
        retry_time_elapsed = retry_time_elapsed + RETRY_PERIOD
        sleep(RETRY_PERIOD)
        retry
      
        retry 
      end      

      # Fetch the CircleCI artifact URLs of this CircleCI job 
      build_num = circleCI_jobs[0]['build_num']
      logger.debug "Fetching artifact URL for build num " + build_num.to_s
      begin 
        response = HTTParty.get("https://circleci.com/api/v1.1/project/github/happy-health/dialog_14683_scratch/" + build_num.to_s + "/artifacts", :headers => {"Circle-Token" => ENV['CIRCLE_CI_API_TOKEN']})
        
        if response.code == 404 
          raise "HTTP Response 404. Check CircleCI API key"  
        end
        if response.code != 200
          raise "HTTP Response #{response.code}"
        end
      rescue RuntimeError => e
        if retry_time_elapsed > MAX_RETRY_TIME_ELAPSED
          logger.debug "Error: max timeout reached." 
          return "max_timeout_reached"
        end 
        logger.debug "Error: #{e}, retrying in #{RETRY_PERIOD} seconds..."
        retry_time_elapsed = retry_time_elapsed + RETRY_PERIOD
        sleep(RETRY_PERIOD)
        retry
      end
      # Filter the artifacts for only the P7 reelase 
      response_parsed = JSON.parse(response)
      artifact_descriptors = response_parsed.select{|descriptor| descriptor["path"] == "~/builds/freertos_retarget/Happy_P7_QSPI_Release/freertos_retarget.bin"}
      artifact_URL = artifact_descriptors[0]["url"]
      logger.debug "Firmware URL: " + artifact_URL

      # Download the firmware from the CircleCI artifact URL
      logger.debug "Downloading application firmware"
      begin 
        download_file(artifact_URL)
      rescue RuntimeError => e
        if retry_time_elapsed > MAX_RETRY_TIME_ELAPSED
          logger.debug "Error: max timeout reached." 
          return "max_timeout_reached"
        end 
        logger.debug "Error: #{e}, retrying in #{RETRY_PERIOD} seconds..."
        retry_time_elapsed = retry_time_elapsed + RETRY_PERIOD
        sleep(RETRY_PERIOD)
        retry
      end

      # Filter the artifacts for only the bootloader
      response_parsed = JSON.parse(response)
      artifact_descriptors = response_parsed.select{|descriptor| descriptor["path"] == "~/builds/ble_suota_loader/DA14683-00-Release_QSPI/ble_suota_loader.bin"}
      artifact_URL = artifact_descriptors[0]["url"]
      logger.debug "Bootloader Firmware URL: " + artifact_URL

      # Download the firmware from the CircleCI artifact URL
      logger.debug "Downloading bootloader firmware"
      begin 
        download_file(artifact_URL)
      rescue RuntimeError => e
        if retry_time_elapsed > MAX_RETRY_TIME_ELAPSED
          logger.debug "Error: max timeout reached." 
          return "max_timeout_reached"
        end 
        logger.debug "Error: #{e}, retrying in #{RETRY_PERIOD} seconds..."
        retry_time_elapsed = retry_time_elapsed + RETRY_PERIOD
        sleep(RETRY_PERIOD)
        retry
      end

    end 

    def download_file(url)
      dir = File.expand_path(File.join(File.dirname(__FILE__), '.', 'lib'))
      logger.debug "Dir to download: " + dir
      # download file without using the memory
      response = nil
      filename = (url.split('/', -1))[-1] # Get the end of the URL, e.g. "freertos_retarget.bin"

      File.open(filename, "w") do |file|
        response = HTTParty.get(url, :headers => {"Circle-Token" => ENV['CIRCLE_CI_API_TOKEN']},  stream_body: true) do |fragment|
          if [301, 302].include?(fragment.code)
            print "skip writing for redirect"
          elsif fragment.code == 200
            print "."
            file.write(fragment)
          else
            raise StandardError, "Non-success status code while streaming #{fragment.code}"
          end
        end
      end
      logger.debug

      pp "Success: #{response.success?}"
      pp File.stat(filename).inspect
      # File.unlink(filename)
      return "success"
    end

    def program_p7
      logger.debug "Flashing over JTAG"
      # Call script that flashes the firmware onto P7
      stdout, stderr, status = Open3.capture3("bash ./reprogram_p7.sh")
      output = stdout + stderr
      logger.debug output
      return output
    end 

    def joulescope_measurement
      logger.debug "Starting Joulescope measurement"
      # output = `python pyjoulescope/bin/trigger.py --start duration --start_duration 1  --end duration --capture_duration 90 --display_stats --count 1 --init_power_off 3 --record`
      output = `python pyjoulescope/bin/trigger.py --start duration --start_duration 1  --end duration --capture_duration 90 --display_stats --count 1 --init_power_off 3`
      logger.debug output
      return output
    end

    # Create a new check run with the status queued
    def create_check_run
      if @payload['repository']['name'] != REPOSITORY_NAME
        return 
      end

      @installation_client.create_check_run(
        # [String, Integer, Hash, Octokit Repository object] A GitHub repository.
        @payload['repository']['full_name'],
        # [String] The name of your check run.
        'P7 uses < 2mA average 90s after reset',
        # [String] The SHA of the commit to check 
        # The payload structure differs depending on whether a check run or a check suite event occurred.
        @payload['check_run'].nil? ? @payload['check_suite']['head_sha'] : @payload['check_run']['head_sha'],
        # [Hash] 'Accept' header option, to avoid a warning about the API not being ready for production use.
        accept: 'application/vnd.github.v3+json'
      )
    end

    # Clones the repository to the current working directory, updates the
    # contents using Git pull, and checks out the ref.
    #
    # full_repo_name  - The owner and repo. Ex: octocat/hello-world
    # repository      - The repository name
    # ref             - The branch, commit SHA, or tag to check out
    def clone_repository(full_repo_name, repository, ref)
      @git = Git.clone("https://x-access-token:#{@installation_token.to_s}@github.com/#{full_repo_name}.git", repository)
      pwd = Dir.getwd()
      Dir.chdir(repository)
      @git.pull
      @git.checkout(ref)
      Dir.chdir(pwd)
    end

    # Saves the raw payload and converts the payload to JSON format
    def get_payload_request(request)
      # request.body is an IO or StringIO object
      # Rewind in case someone already read it
      request.body.rewind
      # The raw text of the body is required for webhook signature verification
      @payload_raw = request.body.read
      begin
        @payload = JSON.parse @payload_raw
      rescue => e
        fail  "Invalid JSON (#{e}): #{@payload_raw}"
      end
    end

    # Instantiate an Octokit client authenticated as a GitHub App.
    # GitHub App authentication requires that you construct a
    # JWT (https://jwt.io/introduction/) signed with the app's private key,
    # so GitHub can be sure that it came from the app an not altererd by
    # a malicious third party.
    def authenticate_app
      payload = {
          # The time that this JWT was issued, _i.e._ now.
          iat: Time.now.to_i,

          # JWT expiration time (10 minute maximum)
          exp: Time.now.to_i + (10 * 60),

          # Your GitHub App's identifier number
          iss: APP_IDENTIFIER
      }

      # Cryptographically sign the JWT.
      jwt = JWT.encode(payload, PRIVATE_KEY, 'RS256')

      # Create the Octokit client, using the JWT as the auth token.
      @app_client ||= Octokit::Client.new(bearer_token: jwt)
    end

    # Instantiate an Octokit client, authenticated as an installation of a
    # GitHub App, to run API operations.
    def authenticate_installation(payload)
      @installation_id = payload['installation']['id']
      @installation_token = @app_client.create_app_installation_access_token(@installation_id)[:token]
      @installation_client = Octokit::Client.new(bearer_token: @installation_token)
    end

    # Check X-Hub-Signature to confirm that this webhook was generated by
    # GitHub, and not a malicious third party.
    #
    # GitHub uses the WEBHOOK_SECRET, registered to the GitHub App, to
    # create the hash signature sent in the `X-HUB-Signature` header of each
    # webhook. This code computes the expected hash signature and compares it to
    # the signature sent in the `X-HUB-Signature` header. If they don't match,
    # this request is an attack, and you should reject it. GitHub uses the HMAC
    # hexdigest to compute the signature. The `X-HUB-Signature` looks something
    # like this: "sha1=123456".
    # See https://developer.github.com/webhooks/securing/ for details.
    def verify_webhook_signature
      their_signature_header = request.env['HTTP_X_HUB_SIGNATURE'] || 'sha1='
      method, their_digest = their_signature_header.split('=')
      our_digest = OpenSSL::HMAC.hexdigest(method, WEBHOOK_SECRET, @payload_raw)
      halt 401 unless their_digest == our_digest

      # The X-GITHUB-EVENT header provides the name of the event.
      # The action value indicates the which action triggered the event.
      logger.debug "---- received event #{request.env['HTTP_X_GITHUB_EVENT']}"
      logger.debug "----    action #{@payload['action']}" unless @payload['action'].nil?
    end

  end

  # Finally some logic to let us run this server directly from the command line,
  # or with Rack. Don't worry too much about this code. But, for the curious:
  # $0 is the executed file
  # __FILE__ is the current file
  # If they are the same—that is, we are running this file directly, call the
  # Sinatra run method
  run! if __FILE__ == $0
end
