#!/bin/sh
set -eu
case "$POSTGRES_TEST_DB" in
  *_test) ;;
  *) echo "POSTGRES_TEST_DB must end in _test" >&2; exit 1 ;;
esac
if [ "$POSTGRES_TEST_DB" = "$POSTGRES_DB" ]; then
  echo "Test database must differ from application database" >&2
  exit 1
fi
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 --set=test_db="$POSTGRES_TEST_DB" <<'SQL'
SELECT format('CREATE DATABASE %I', :'test_db') \gexec
SQL
