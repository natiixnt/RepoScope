import express from 'express';
import { validateToken } from '../services/auth';
import { dbHealth } from '../infra/db';

const app = express();

app.get('/health', (_req, res) => {
  const authOk = validateToken('token');
  const dbOk = dbHealth();
  res.json({ authOk, dbOk });
});

app.listen(3000, () => {
  console.log('server started');
});
