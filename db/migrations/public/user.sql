
create table public.user (
	user_id SERIAL PRIMARY KEY,
	username varchar(100) not null,
	email varchar(255) unique  not null,
	heahpassword varchar(255) not null, 
	role varchar(50) default 'viewer',
	is_active boolean default true, 
	created_at TIMESTAMPTZ,
	updated_at TIMESTAMPTZ
)
