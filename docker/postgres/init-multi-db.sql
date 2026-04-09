SELECT 'CREATE DATABASE "chathistory"'
WHERE NOT EXISTS (
  SELECT FROM pg_database WHERE datname = 'chathistory'
)\gexec
