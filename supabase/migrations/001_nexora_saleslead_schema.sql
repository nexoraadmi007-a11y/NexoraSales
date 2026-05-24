create extension if not exists "pgcrypto";
create extension if not exists "vector";

create schema if not exists nexora_saleslead;
set search_path to nexora_saleslead, public;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  telegram_id text unique not null,
  full_name text,
  username text,
  role text not null default 'agent' check (role in ('admin', 'agent')),
  status text not null default 'active' check (status in ('active', 'disabled')),
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique,
  business_name text not null,
  industry text not null check (industry in ('school', 'solar')),
  location text not null,
  phone_number text,
  email text,
  website text,
  social_url text,
  contact_person text,
  estimated_organization_size text,
  source text not null,
  source_url text,
  raw_payload jsonb not null default '{}'::jsonb,
  assigned_agent_id uuid references users(id) on delete set null,
  status text not null default 'new' check (status in ('new', 'assigned', 'contacted', 'qualified', 'won', 'lost', 'archived')),
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists conversations (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads(id) on delete cascade,
  agent_id uuid references users(id) on delete set null,
  channel text not null default 'telegram',
  last_message text,
  last_interaction_at timestamptz,
  status text not null default 'open' check (status in ('open', 'waiting', 'done', 'closed')),
  metadata jsonb not null default '{}'::jsonb,
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists followups (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  followup_type text not null,
  next_followup_at timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'sent', 'skipped', 'cancelled')),
  guidance text,
  sent_at timestamptz,
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists reports (
  id uuid primary key default gen_random_uuid(),
  report_type text not null,
  report_date date not null,
  file_path text,
  total_leads integer not null default 0,
  school_count integer not null default 0,
  solar_count integer not null default 0,
  delivery_status text not null default 'pending' check (delivery_status in ('pending', 'generated', 'delivered', 'failed')),
  telegram_message_id bigint,
  delivered_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (report_type, report_date)
);

create table if not exists lead_scores (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads(id) on delete cascade,
  lead_score integer not null check (lead_score between 0 and 100),
  operational_complexity_score integer not null check (operational_complexity_score between 0 and 100),
  saas_potential_score integer not null check (saas_potential_score between 0 and 100),
  likely_operational_challenges text,
  suggested_nexora_entry_point text,
  suggested_conversation_angle text,
  notes text,
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists activity_logs (
  id uuid primary key default gen_random_uuid(),
  activity_type text not null,
  message text not null,
  severity text not null default 'info' check (severity in ('debug', 'info', 'warning', 'error', 'critical')),
  metadata jsonb not null default '{}'::jsonb,
  created_by text not null default 'system',
  created_at timestamptz not null default now()
);

create table if not exists agent_sessions (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references users(id) on delete cascade,
  active_lead_id uuid references leads(id) on delete set null,
  telegram_chat_id text,
  state jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists conversation_memories (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  content text not null,
  embedding vector(1536) not null,
  metadata jsonb not null default '{}'::jsonb,
  created_by text not null default 'system',
  updated_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = nexora_saleslead, public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger trg_users_updated_at before update on users for each row execute function set_updated_at();
create trigger trg_leads_updated_at before update on leads for each row execute function set_updated_at();
create trigger trg_conversations_updated_at before update on conversations for each row execute function set_updated_at();
create trigger trg_followups_updated_at before update on followups for each row execute function set_updated_at();
create trigger trg_reports_updated_at before update on reports for each row execute function set_updated_at();
create trigger trg_lead_scores_updated_at before update on lead_scores for each row execute function set_updated_at();
create trigger trg_agent_sessions_updated_at before update on agent_sessions for each row execute function set_updated_at();
create trigger trg_conversation_memories_updated_at before update on conversation_memories for each row execute function set_updated_at();

create index if not exists idx_leads_industry_status on leads(industry, status);
create index if not exists idx_leads_location on leads(location);
create index if not exists idx_leads_assigned_agent on leads(assigned_agent_id);
create index if not exists idx_conversations_lead on conversations(lead_id);
create index if not exists idx_conversations_agent_status on conversations(agent_id, status);
create index if not exists idx_followups_due on followups(status, next_followup_at);
create index if not exists idx_followups_conversation on followups(conversation_id);
create index if not exists idx_reports_date on reports(report_type, report_date desc);
create index if not exists idx_lead_scores_lead on lead_scores(lead_id);
create index if not exists idx_activity_logs_type_created on activity_logs(activity_type, created_at desc);
create index if not exists idx_agent_sessions_agent on agent_sessions(agent_id, ended_at);
create index if not exists idx_agent_sessions_active_lead on agent_sessions(active_lead_id);
create index if not exists idx_conversation_memories_conversation on conversation_memories(conversation_id);
create index if not exists idx_conversation_memories_embedding on conversation_memories using ivfflat (embedding vector_cosine_ops) with (lists = 100);

alter table users enable row level security;
alter table leads enable row level security;
alter table conversations enable row level security;
alter table followups enable row level security;
alter table reports enable row level security;
alter table lead_scores enable row level security;
alter table activity_logs enable row level security;
alter table agent_sessions enable row level security;
alter table conversation_memories enable row level security;
