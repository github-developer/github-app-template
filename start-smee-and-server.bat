taskkill /f /IM ruby.exe
taskkill /f /IM node.exe
start cmd.exe @cmd /k "smee -u http://ec2-52-53-175-67.us-west-1.compute.amazonaws.com:3000/e8uoHKbzBo5VnHaA --path /event_handler --port 3000" 
C:\Users\Andrew\AppData\Local\Atlassian\SourceTree\git_local\usr\bin\mintty.exe -o MSYSTEM=MINGW32 /usr/bin/bash -l sinatra-server-caller.sh