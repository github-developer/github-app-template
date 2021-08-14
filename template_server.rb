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
require 'thread'
require 'date'
require 'aws-sdk-s3'

set :port, 3000
set :bind, '0.0.0.0'

ABOVE_THIS_CURRENT_USAGE_THRESHOLD_IN_AMPS_FAILS_TEST = 0.005
MEASUREMENT_DURATION = 90
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

  semaphore = Mutex.new
  # For some reason, Github submits TWO check_run events per pull_request event, 
  # so work around the issue by refusing to measure the same commit twice in a row
  last_commit_hash = ""; 

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
        a = Thread.new {
          semaphore.synchronize {
            case @payload['action']          
            when 'created'
              # For some reason, Github submits TWO check_run events per pull_request event, 
              # so work around the issue by refusing to measure the same commit twice in a row
              if last_commit_hash != commit_hash = @payload['check_run']['head_sha']
                initiate_check_run
                last_commit_hash = commit_hash = @payload['check_run']['head_sha']
              end
            when 'rerequested'
              create_check_run
            end
          }
        }
      end
    when 'check_suite'
      # A new check_suite has been created. Create a new check run with status queued
      if @payload['action'] == 'requested' || @payload['action'] == 'rerequested'
        create_check_run
      end
    when 'pull_request'
      if @payload['action'] == 'opened' || @payload['action'] == 'synchronize'
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
            title: "Timed out. Did CirclCI Build successfully?",
            summary: "Firmware download did not finish after #{MAX_RETRY_TIME_ELAPSED}s. Did CircleCI build successfully?",
          },
          accept: 'application/vnd.github.v3+json'
        )
        return result
      elsif result == "job-failed-blocked-canceled"

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
            title: "No firmware to measure",
            summary: "CircleCI job failed/blocked/canceled. No firmware to measure.",
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
            title: "cannot open gdb interface. A cable is disconnected or the power is off",
            summary: "cannot open gdb interface. A cable is disconnected or the power is off. Did the RESET pin inverter light on fire?",
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
            title: "unknown error",
            summary: "Unknown error. Details below",
            text: output
          },
          accept: 'application/vnd.github.v3+json'
        )

        return "program_p7_failed"
      end

      stdout, stderr, status = Open3.capture3("taskkill /f /im joulescope.exe")

      # Prevent duplicate files from taking up a lot of disk space 
      `rm -rf *.jls`
      `rm -rf *.png`

      # Turn on Joulescope and start measuring 
      result = joulescope_measurement

      if (result.downcase).include?("error")
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
            title: "Joulescope error",
            summary: "Joulescope error. Details below. Is Joulescope connected "\
            "and no application other than this script using it? Close Joulescope GUI.",
            text: result
          },
          accept: 'application/vnd.github.v3+json'
        )

        return "joulescope_measurement_failed"
      end
      
      
      date_time = (DateTime.now)
      date_time = date_time.new_offset('+00:00')
      image_file_name = date_time.strftime("%Y%m%d_%H%M%S.png")
      jls_file_name = `ls *.jls`
      jls_file_name = jls_file_name[0..-2] #remove the /r/n
      plot_first_few_seconds_file_name = date_time.strftime("%Y%m%d_%H%M%S_first_few_s.png")

      logger.debug "Taking Joulescope screenshot"
      # Open Joulescope window       
      pid = spawn("\"C:\\Program Files (x86)\\Joulescope\\joulescope.exe\" ./#{jls_file_name}")
      Process.detach(pid)
      sleep(10) # Wait for the Joulescope window to open and plot all data. Computer is slow. 
      # Use screen capture program 
      stdout, stderr, status = Open3.capture3("screenCapture.bat #{image_file_name} Joulescope:")
      output = stdout + stderr
      logger.debug output

      joulescope_output_parsed = eval(result)
      current_mean = joulescope_output_parsed[:"current_mean(A)"].to_f 
      if current_mean > ABOVE_THIS_CURRENT_USAGE_THRESHOLD_IN_AMPS_FAILS_TEST
        github_conclusion = "failure"
      else
        github_conclusion = "success"
      end

      # Make bar graph of the last few measurements
      commit_hash = @payload['check_run']['head_sha'][0..7]
      user = @payload['sender']['login']
      new_csv_line = date_time.strftime("%Y-%m-%d") + "," + commit_hash + "," + user + "," + current_mean.to_s
      logger.debug "new_csv_line: " + new_csv_line
      stdout, stderr, status = Open3.capture3("python make_bar_chart.py #{plot_first_few_seconds_file_name} '#{new_csv_line}'")
      output = stdout + stderr
      logger.debug output
      
      # Upload files
      jls_URL = aws_s3_upload_file(jls_file_name)
      img_URL = aws_s3_upload_file(image_file_name)
      plot_first_few_s_URL = aws_s3_upload_file(plot_first_few_seconds_file_name)

      `taskkill /f /im joulescope.exe`
      
      full_repo_name = @payload['repository']['full_name']
      repository     = @payload['repository']['name']
      head_sha       = @payload['check_run']['head_sha']
      
      # Mark the check run as complete! And if there are warnings, share them.
      @installation_client.update_check_run(
        @payload['repository']['full_name'],
        @payload['check_run']['id'],
        status: 'completed',
        ## Conclusion: 
        #  Can be one of action_required, cancelled, failure, neutral, success, 
        #  skipped, stale, or timed_out. When the conclusion is action_required, 
        #  additional details should be provided on the site specified by details_url.
        conclusion: github_conclusion, 
        output: {
          title: "#{current_mean} A mean",
          summary: "P7 programmed and measured successfully. </p><a href=\"#{jls_URL}\">Download JLS file to see in Joulescope GUI (deleted after 48h)</a></p><img src=\"#{img_URL}\"></p><img src=\"#{plot_first_few_s_URL}\">",
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
          response = HTTParty.get('https://circleci.com/api/v1.1/project/github/happy-health/dialog_14683_scratch?limit=100&offset=0', :headers => {"Circle-Token" => ENV['CIRCLE_CI_API_TOKEN']})
          
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
        circleCI_jobs_for_this_commit = response_parsed.select{|job| job["vcs_revision"] == @payload['check_run']['head_sha']}
        circleCI_jobs_failed = circleCI_jobs_for_this_commit.select{|job| job["status"] == "canceled" || job["status"] == "failed" || job["status"] == "blocked"}
        circleCI_jobs_pack_images = circleCI_jobs_for_this_commit.select{|job| job["build_parameters"]["CIRCLE_JOB"] == "pack_images"}

        if circleCI_jobs_failed.length > 0
          # One of the CircleCI jobs was canclled or failed. 
          # Failed job = did not build properly 
          # cancelled job = A newer commit in the same pull request was submitted before this job could finish 
          # (there are two different spellings for cancelled. CircleCI uses "canceled" and Github uses "cancelled")
          # in either case, this entire script should just stop for this Github commit 
          logger.debug "At least one CircleCI job failed/blocked/canceled for commit " + @payload['check_run']['head_sha'][0..6] 
          return "job-failed-blocked-canceled"
        elsif circleCI_jobs_pack_images.length() == 0
          raise "CircleCI pack_images job not created yet. Commit " + @payload['check_run']['head_sha'][0..6]
        else  
          # Check if job is finished yet 
          if circleCI_jobs_pack_images[0]["status"] != "success"
            raise "pack_images job status: " + circleCI_jobs_pack_images[0]["status"]
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
      build_num = circleCI_jobs_pack_images[0]['build_num']
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
      stdout, stderr, status = Open3.capture3("python pyjoulescope/bin/trigger.py --start duration --start_duration 1  --end duration --capture_duration #{MEASUREMENT_DURATION} --display_stats --count 1 --init_power_off 3 --record")
      output = stdout + stderr
      logger.debug output
      return output
    end

    # Uploads an object to a bucket in Amazon Simple Storage Service (Amazon S3).
    #
    # Prerequisites:
    #
    # - An S3 bucket.
    # - An object to upload to the bucket.
    #
    # @param s3_client [Aws::S3::Client] An initialized S3 client.
    # @param bucket_name [String] The name of the bucket.
    # @param object_key [String] The name of the object.
    # @return [Boolean] true if the object was uploaded; otherwise, false.
    # @example
    #   exit 1 unless object_uploaded?(
    #     Aws::S3::Client.new(region: 'us-east-1'),
    #     'doc-example-bucket',
    #     'my-file.txt'
    #   )

    def aws_s3_object_uploaded?(s3_resource, bucket_name, object_key, file_path)
      object = s3_resource.bucket(bucket_name).object(object_key)
  
      if file_path.include?(".png")
        object.upload_file(file_path, {content_type: "image/png"})
      else
        object.upload_file(file_path)
      end
      
      return true
    rescue StandardError => e
      logger.debug "Error uploading object: #{e.message}"
      return false
    end
    
    # Full example call:
    def aws_s3_upload_file(filename)
      bucket_name = 'power-tester-artifacts'
      object_key = filename
      region = 'us-west-1'
      s3_client = Aws::S3::Resource.new(region: region,
        access_key_id: ENV['AWS_S3_API_KEY_ID'],
        secret_access_key: ENV['AWS_SECRET_ACCESS_KEY'])
    
      if aws_s3_object_uploaded?(s3_client, bucket_name, object_key, object_key)
        logger.debug "Object '#{object_key}' uploaded to bucket '#{bucket_name}'."
        return "https://" + bucket_name + ".s3." + region + ".amazonaws.com/" + object_key
      else
        logger.debug "Object '#{object_key}' not uploaded to bucket '#{bucket_name}'."
        return ""
      end
    end

    # Create a new check run with the status queued
    def create_check_run
      if @payload['repository']['name'] != REPOSITORY_NAME
        return 
      end

      # The payload structure differs depending on whether a check run or a check suite event occurred.
      if @payload['check_run'] != nil 
        commit_hash = @payload['check_run']['head_sha']
      elsif @payload['check_suite'] != nil
        commit_hash = @payload['check_suite']['head_sha']
      elsif @payload['pull_request'] != nil
        commit_hash = @payload['pull_request']['head']['sha']
      end

      @installation_client.create_check_run(
        # [String, Integer, Hash, Octokit Repository object] A GitHub repository.
        @payload['repository']['full_name'],
        # [String] The name of your check run.
        "P7 avg < #{ABOVE_THIS_CURRENT_USAGE_THRESHOLD_IN_AMPS_FAILS_TEST}A #{MEASUREMENT_DURATION}s after reset",
        # [String] The SHA of the commit to check 
        commit_hash, 
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
      # @installation_id = payload['installation']['id']
      @installation_id = 18537730 # hardcoded since it doesn't come in the API for "pull_request" events
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
      logger.debug "----    action: #{@payload['action']}" unless @payload['action'].nil?
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
