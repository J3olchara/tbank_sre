CREATE TABLE tasks (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 title VARCHAR(200) NOT NULL CHECK (length(trim(title)) > 0),
 description TEXT NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
 status VARCHAR(10) NOT NULL DEFAULT 'todo' CHECK (status IN ('todo', 'doing', 'done')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
