import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { readFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../../',import.meta.url));
const db = await PGlite.create();
const port = Number(process.env.TEST_DATABASE_PORT || '55439');
const server = new PGLiteSocketServer({db,host:'127.0.0.1',port});
try {
  await db.exec('CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);');
  await db.exec(await readFile(new URL('../migrations/001_initial.sql',import.meta.url),'utf8'));
  await db.exec("INSERT INTO auth.users VALUES('00000000-0000-0000-0000-000000000001'); INSERT INTO private.staff_members(user_id,display_name) VALUES('00000000-0000-0000-0000-000000000001','Test staff');");
  await server.start();
  const python = process.env.TEST_PYTHON || path.join(root,'backend','.venv',process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const child = spawn(python,['-m','pytest','tests/test_integration.py','-q'],{
    cwd:path.join(root,'backend'),stdio:'inherit',env:{...process.env,TEST_DATABASE_URL:`postgresql://postgres@127.0.0.1:${port}/postgres?sslmode=disable`},
  });
  process.exitCode = await new Promise((resolve,reject) => { child.on('error',reject); child.on('exit',code => resolve(code ?? 1)); });
} finally { await server.stop(); await db.close(); }
