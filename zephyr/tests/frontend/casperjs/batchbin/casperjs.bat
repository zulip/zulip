@ECHO OFF
set CASPER_PATH=%~dp0..\
set CASPER_BIN=%CASPER_PATH%bin\

set PHANTOMJS_NATIVE_ARGS=(--cookies-file --config --debug --disk-cache --ignore-ssl-errors --load-images --load-plugins --local-storage-path --local-storage-quota --local-to-remote-url-access --max-disk-cache-size --output-encoding --proxy --proxy-auth --proxy-type --remote-debugger-port --remote-debugger-autorun --script-encoding --web-security)

set PHANTOM_ARGS=
set CASPER_ARGS=

:Loop
if "%1"=="" goto Continue
	set IS_PHANTOM_ARG=0
	for %%i in %PHANTOMJS_NATIVE_ARGS% do (
		if "%%i"=="%1" set IS_PHANTOM_ARG=1
	)
	if %IS_PHANTOM_ARG%==0 set CASPER_ARGS=%CASPER_ARGS% %1
	if %IS_PHANTOM_ARG%==1 set PHANTOM_ARGS=%PHANTOM_ARGS% %1
shift
goto Loop
:Continue

call phantomjs%PHANTOM_ARGS% %CASPER_BIN%bootstrap.js --casper-path=%CASPER_PATH% --cli%CASPER_ARGS%