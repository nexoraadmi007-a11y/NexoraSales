grant usage on schema nexora_saleslead to anon, authenticated, service_role;
grant all on all tables in schema nexora_saleslead to anon, authenticated, service_role;
grant all on all routines in schema nexora_saleslead to anon, authenticated, service_role;
grant all on all sequences in schema nexora_saleslead to anon, authenticated, service_role;

alter default privileges for role postgres in schema nexora_saleslead grant all on tables to anon, authenticated, service_role;
alter default privileges for role postgres in schema nexora_saleslead grant all on routines to anon, authenticated, service_role;
alter default privileges for role postgres in schema nexora_saleslead grant all on sequences to anon, authenticated, service_role;

alter role authenticator set pgrst.db_schemas = 'public, graphql_public, nexora_saleslead';
notify pgrst, 'reload config';
notify pgrst, 'reload schema';
