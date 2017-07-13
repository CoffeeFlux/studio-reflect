-- Requires folders within ServerStorage and ReplicatedStorage both called 
-- 'Modules', as well as a modulescript within Workspace called 'ProjectName'
-- that just returns the project name.

SERVER_ADDRESS = 'http://127.0.0.1:8081'
POLL_INTERVAL = 1

--------------------------------------------------------------------------------

print 'Running studio-reflect plugin!'
wait 1 -- Standard wait for loading etc.

httpService = game\GetService 'HttpService'
serverStorage = game\GetService 'ServerStorage'
replicatedStorage = game\GetService 'ReplicatedStorage'
workspace = game\GetService 'Workspace'

errors = {
	invalidInstruction: 'Instruction \'%s\' was sent over, yet is invalid'
	invalidFolder: 'Directory \'%s\' was sent over for use, yet is invalid'
	fileExists: 'Attempt to create file \'%s\' within \'%s\' folder failed, 
as this file already exists'
	fileDoesntExist: 'Attempt to perform operation on file \'%s\' within 
\'%s\' folder failed, as this file does not exist'
	pollingFailed: 'Attempt to poll local http server failed, error: %s'
}

serverModules = serverStorage\WaitForChild 'Modules'
replicatedModules = replicatedStorage\WaitForChild 'Modules'

projectName = require workspace\WaitForChild 'ProjectName'
projectNameJSON = httpService\JSONEncode {'project_name': projectName}

httpActive = ->
	success, response = pcall -> 
		httpService\PostAsync SERVER_ADDRESS, projectNameJSON
	return success

-- Attempt to establish connection with the python server
while not httpActive!
	wait 1

print 'Connection established with server running at ' .. SERVER_ADDRESS

serverModules\ClearAllChildren!
replicatedModules\ClearAllChildren!

parseResponse = (body) ->
	for _, entry in pairs body
		instruction = entry.instruction
		filename = entry.filename
		folderName = entry.directory
		local folder
		if folderName == 'server'
			folder = serverModules
		elseif folderName == 'replicated'
			folder = replicatedModules
		else
			print string.format errors.invalidFolder, folderName
			return

		if instruction == 'create'
			if folder\FindFirstChild filename
				print string.format errors.fileExists, filename, folderName
				return
			file = Instance.new 'ModuleScript'
			file.Name = filename
			file.Parent = folder
			file.Source = entry.contents
		elseif instruction == 'modify'
			file = folder\FindFirstChild filename
			unless file
				print string.format errors.fileDoesntExist, filename, folderName
				return
			file.Source = entry.contents
		elseif instruction == 'delete'
			file = folder\FindFirstChild filename
			unless file
				print string.format errors.fileDoesntExist, filename, folderName
				return
			file\Destroy!
		else
			print string.format errors.invalidInstruction, instruction

-- Connection presumably established, start fetching instructions
Spawn ->
	while wait POLL_INTERVAL
		success, response = pcall -> httpService\GetAsync SERVER_ADDRESS
		unless success
			print string.format errors.pollingFailed, response
			continue
		parseResponse httpService\JSONDecode response
