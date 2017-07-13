# WATCHDOG MUST BE INSTALLED FOR THIS TO WORK

# I should probably add real error-handling at some point

# Folder containing all active projects. Names, obviously, must be unique, and
# scripts for a given project will only be loaded if the studio file has the
# same name. Within each project folder, there must be folders called
# "replicated" and "server". Only files within those with a ".moon" extension
# will be compiled and sent over
BASE_FOLDER = 'Q:\Ryan\Documents\RBLX_SOURCE\projects'

# Path to mooonscript `moonc.exe` binary; if empty it assumes it's on your path
MOONSCRIPT_BINARY = ''

# Every file is prefixed with this - newlines must be added manually if desired
# Should probably be in the project config itself, but whatever
PREFIX = "local use = require(game:GetService('ReplicatedStorage'):FindFirstChild('Modules'):FindFirstChild('ModuleLoader')).GetModule\n"

# Tuple of file names (without extensions) to not prefix
PREFIX_BLACKLIST = ('ModuleLoader')

# Address and port
SERVER_ADDRESS = ('127.0.0.1', 8081)

################################################################################

import time, json, http.server, os, subprocess, glob
from urllib.parse import urlparse, parse_qs
from cgi import parse_header, parse_multipart
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

instructions = []

def get_instructions_json():
	dump = json.dumps(instructions)
	del instructions[:]
	return dump

def compile(src_path):
	binary = MOONSCRIPT_BINARY if MOONSCRIPT_BINARY else "moonc"
	complete = subprocess.run([binary, '-p', src_path], stdout=subprocess.PIPE)
	# Decoding as unicode here may have edge-case issues, but it should be fine probably
	return complete.stdout.decode('utf-8')

def get_name(src_path):
	return os.path.splitext(os.path.basename(src_path))[0]

def get_extension(src_path):
	return os.path.splitext(os.path.basename(src_path))[1]

def get_contents(src_path):
	# Super lazy way to ensure the file really exists by the time I try to read it
	# Someone please make this less bad, thanks
	time.sleep(0.01)
	if get_extension(src_path) == '.moon':
		contents = compile(src_path)
	else:
		f = open(src_path)
		contents = f.read()
		f.close()

	if not (get_name(src_path) in PREFIX_BLACKLIST):
		contents = PREFIX + contents

	return contents

def assert_dir(dir_path):
	if not os.path.exists(dir_path):
		# I love race conditions
		os.makedirs(dir_path)

class MoonHandler(PatternMatchingEventHandler):
	patterns = ["*.moon", "*.lua"]
	ignore_directories = True
	case_sensitive = True

	def __init__(self, directory):
		super().__init__()
		self.directory = directory

	def created(self, src_path):
		instructions.append({
			'instruction': 'create',
			'filename': get_name(src_path),
			'directory': self.directory,
			'contents': get_contents(src_path)
		})

	def modified(self, src_path):
		instructions.append({
			'instruction': 'modify',
			'filename': get_name(src_path),
			'directory': self.directory,
			'contents': get_contents(src_path)
		})

	def deleted(self, src_path):
		instructions.append({
			'instruction': 'delete',
			'filename': get_name(src_path),
			'directory': self.directory
		})

	def on_created(self, event):
		self.created(os.path.join(BASE_FOLDER, self.directory, event.src_path))

	def on_modified(self, event):
		self.modified(os.path.join(BASE_FOLDER, self.directory, event.src_path))

	def on_deleted(self, event):
		self.deleted(os.path.join(BASE_FOLDER, self.directory, event.src_path))

	def on_moved(self, event):
		self.deleted(os.path.join(BASE_FOLDER, self.directory, event.src_path))
		self.created(os.path.join(BASE_FOLDER, self.directory, event.dest_path))

ServerHandler = MoonHandler('server')
ReplicatedHandler = MoonHandler('replicated')

class HTTPServer_RequestHandler(http.server.BaseHTTPRequestHandler):

	def do_HEAD(self):
		self.send_response(200)
		self.send_header('content-type', 'application/json')
		self.end_headers()

	def do_GET(self):
		self.do_HEAD()
		message = get_instructions_json()
		self.wfile.write(bytes(message, 'utf8'))

	def do_POST(self):
		self.do_HEAD()

		# Parse POST vars
		ctype, pdict = parse_header(self.headers['content-type'])
		if ctype == 'multipart/form-data':
			postvars = parse_multipart(self.rfile, pdict)
		elif ctype == 'application/x-www-form-urlencoded':
			length = int(self.headers['content-length'])
			postvars = parse_qs(self.rfile.read(length), keep_blank_values=1)
		elif ctype == 'application/json':
			length = int(self.headers['content-length'])
			postvars = {'data': self.rfile.read(length)}
		else:
			postvars = {}
		body = json.loads(postvars['data'])

		print('Connection established with plugin')

		# Reset and set up everything
		del instructions[:]

		project_name = body['project_name']
		project_dir = os.path.join(BASE_FOLDER, project_name)
		assert_dir(project_dir)
		server_dir = os.path.join(project_dir, 'server')
		assert_dir(server_dir)
		replicated_dir = os.path.join(project_dir, 'replicated')
		assert_dir(replicated_dir)

		server_observer = Observer()
		server_observer.schedule(ServerHandler, path=server_dir, recursive=True)
		replicated_observer = Observer()
		replicated_observer.schedule(ReplicatedHandler, path=replicated_dir, recursive=True)

		# Send a clean list of files
		for filename in glob.glob(server_dir + '/**/*.moon', recursive=True):
			ServerHandler.created(os.path.join(server_dir, filename))
		for filename in glob.glob(server_dir + '/**/*.lua', recursive=True):
			ServerHandler.created(os.path.join(server_dir, filename))
		for filename in glob.glob(replicated_dir + '/**/*.moon', recursive=True):
			ReplicatedHandler.created(os.path.join(replicated_dir, filename))
		for filename in glob.glob(replicated_dir + '/**/*.lua', recursive=True):
			ReplicatedHandler.created(os.path.join(replicated_dir, filename))

		# Send empty response
		message = ''
		self.wfile.write(bytes(message, 'utf8'))

		server_observer.start()
		replicated_observer.start()

		# try:
		# 	while True:
		# 		time.sleep(1)
		# except KeyboardInterrupt:
		# 	server_observer.stop()
		# 	replicated_observer.stop()

		# server_observer.join()
		# replicated_observer.join()

def launch():
	httpd = http.server.HTTPServer(SERVER_ADDRESS, HTTPServer_RequestHandler)
	httpd.serve_forever()
	return httpd

print('Launching studio-reflect httpd')
httpd = launch()


