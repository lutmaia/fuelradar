-- Lacre do teste final da modelagem v2 (Marco 10; desenho, seção 6.2, e protocolo da modelagem, seção 7).
-- Cada leitura do teste grava uma linha aqui antes de os dados serem devolvidos; o relatório final
-- conta as linhas. Só o papel administrativo escreve; a API não lê esta tabela.

CREATE TABLE holdout_access (
    access_id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    accessed_at timestamptz NOT NULL DEFAULT now(),
    code_sha    text,
    purpose     text NOT NULL CHECK (length(trim(purpose)) > 0),
    data_hash   text NOT NULL,
    row_count   integer NOT NULL,
    first_week  date NOT NULL,
    last_week   date NOT NULL
);
