#!/usr/bin/env python

import os, base64, multiprocessing, json, traceback
import subprocess32 as subprocess

class TestFailed(Exception):
  pass

def fail(s, *args):
  text = s.format(*args)
  print("FATAL: {}".format(text))
  raise TestFailed(text)

def child_fail(s):
  fail('{}\n\n{}', s, traceback.format_exc())

def write_private_key():
  with open('private.pem', 'w') as f:
    f.write(base64.b64decode(os.environ['PRIVATE_KEY']))

def remove_private_key():
  os.remove('private.pem')

def hide_private_key():
  del os.environ['PRIVATE_KEY']
  assert not subprocess.run('echo $PRIVATE_KEY', stdout=subprocess.PIPE, shell=True).stdout.strip()

def decrypt_file(infile, outfile):
  subprocess.run([
    'openssl',
    'smime',
    '-decrypt',
    '-binary',
    '-inkey',
    'private.pem',
    '-inform',
    'DEM',
    '-in',
    infile,
    '-out',
    outfile,
  ]).check_returncode()

def decrypt_files(application_root):
  write_private_key()
  decrypted = []
  for root, dirs, files in os.walk(application_root):
      for file in files:
        if file.endswith('.enc'):
          infile = os.path.join(root, file)
          outfile = infile[:-4]
          decrypt_file(infile, outfile)
          decrypted.append(outfile)
  remove_private_key()
  return decrypted

def remove_files(files):
  for file in files:
    os.remove(file)

def check_applications():
  for username in os.listdir('applications'):
    check_application(username)

def check_application(username):
  root = os.path.join('applications', username)
  decrypted = decrypt_files(root)
  try:
    start_verify_process(root)
  finally:
    remove_files(decrypted)

def exists(root, file):
  return os.path.exists(os.path.join(root, file))

def raise_if_not_exists(root, file):
  if not exists(root, file):
    fail('{} is required but not found!'.format(file))

def raise_if_empty(root, file, min_length=100):
  with open(os.path.join(root, file)) as f:
    content = f.read()
  if len(content) < 100:
    fail('{} should be at least {} chars long', file, min_length)

def raise_if_not_executable(root, file):
  if not os.access(os.path.join(root, file), os.X_OK):
    fail('{} is not executable', file)

def _verify_application(root):
  for required in ['application.json', 'essay.txt', 'challenge']:
    raise_if_not_exists(root, required)

  required_keys = {
    'first_name',
    'last_name',
    'resume',
    'university',
    'grad_year',
    'linkedin',
    'email'
  }
  with open(os.path.join(root, 'application.json')) as f:
    try:
      application = json.loads(f.read())
    except ValueError:
      fail('invalid JSON in application.json')

  missing = required_keys - set(application.keys())
  if missing:
    fail('missing keys in application.json: {}', missing)

  raise_if_empty(root, 'essay.txt')

  index = os.path.join('challenge', 'index.html')
  build = os.path.join('challenge', 'build.sh')

  if exists(root, build):
    raise_if_not_executable(root, build)
    result = subprocess.run(os.path.join(root, build), stdout=subprocess.PIPE, timeout=30)
    if result.returncode != 0:
      fail('{} exited with nonzero status {}', build, result.returncode)
    if not result.stdout:
      fail('{} did not output anything', build)
  elif exists(root, index):
    raise_if_empty(root, index)
  else:
    fail('neither {} not {} is present', index, build)

def verify_application(root):
  try:
    _verify_application(root)
  except TestFailed:
    raise
  except Exception:
    child_fail('application could not be verified')

def start_verify_process(root):
  pool = multiprocessing.Pool(processes=1)
  pool.apply(verify_application, args=(root,))
  pool.close()
  pool.join()

def run():
  try:
    check_applications()
  except TestFailed:
    print('This application is not valid.')
    exit(1)
  else:
    print('This application is valid!')

if __name__ == '__main__':
  run()
