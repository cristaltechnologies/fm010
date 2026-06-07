-- ============================================================
-- FM010 Schema — PTX and MFA tables
-- Replaces ISAM files: fl/ptx and fl/mfa
-- ============================================================

-- -------------------------------------------------------
-- PTX : Global Parametric File  (recptx.cp)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS ptx (

    -- Primary key  (PTX-KEY PIC X(12))
    ptx_key             CHAR(12)    NOT NULL,

    -- Alternate key (PTX-ALT-KEY1 = ptx_code1 + ptx_desc + ptx_subdesc)
    ptx_code1           CHAR(2)     NOT NULL DEFAULT '  ',
    ptx_desc            CHAR(25)    NOT NULL DEFAULT '                         ',
    ptx_subdesc         CHAR(25)    NOT NULL DEFAULT '                         ',

    -- Payload (PTX-OTHER-DATA PIC X(700))
    -- Stored as text; Python unpacks into typed sub-fields on read
    ptx_other_data      CHAR(700)   NOT NULL DEFAULT '',

    -- Derived / computed columns (REDEFINES of PTX-KEY)
    ptx_code            CHAR(2)     GENERATED ALWAYS AS (LEFT(ptx_key,2))           STORED,
    ptx_minor_key       CHAR(10)    GENERATED ALWAYS AS (SUBSTRING(ptx_key FROM 3)) STORED,

    CONSTRAINT pk_ptx PRIMARY KEY (ptx_key)
);

-- Alternate index (ALTERNATE RECORD KEY WITH DUPLICATES)
CREATE INDEX IF NOT EXISTS idx_ptx_alt_key1
    ON ptx (ptx_code1, ptx_desc, ptx_subdesc);

CREATE INDEX IF NOT EXISTS idx_ptx_code
    ON ptx (ptx_code);

-- -------------------------------------------------------
-- MFA : Master File Accounts  (recmfa.cp)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS mfa (

    -- Primary key  (MFA-GAN PIC X(12))
    mfa_gan             CHAR(12)    NOT NULL,

    -- Passive data (MFA-PASSIVE-DATA, stored as individual columns)
    mfa_gan_desc        CHAR(25)    NOT NULL DEFAULT '                         ',
    mfa_main_desc       CHAR(25)    NOT NULL DEFAULT '                         ',
    mfa_dr_cr_flag      SMALLINT    NOT NULL DEFAULT 0,
    mfa_left_chapter    CHAR(8)     NOT NULL DEFAULT '        ',
    mfa_right_chapter   CHAR(8)     NOT NULL DEFAULT '        ',
    mfa_currency_code   SMALLINT    NOT NULL DEFAULT 0,
    mfa_active_flag     SMALLINT    NOT NULL DEFAULT 0,

    -- Active data (balances)
    mfa_dr              NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_cr              NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_frn_dr          NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_frn_cr          NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_dr_lm           NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_cr_lm           NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_frn_dr_lm       NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_frn_cr_lm       NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_frn_bal_ly      NUMERIC(11,2) NOT NULL DEFAULT 0,
    mfa_prev_2_years    NUMERIC(11,2) NOT NULL DEFAULT 0,

    -- Monthly tables stored as JSONB arrays (13 months each)
    mfa_cy              NUMERIC(11,2)[] NOT NULL DEFAULT ARRAY[]::NUMERIC[],
    mfa_ly              NUMERIC(11,2)[] NOT NULL DEFAULT ARRAY[]::NUMERIC[],
    mfa_bud             NUMERIC(11,2)[] NOT NULL DEFAULT ARRAY[]::NUMERIC[],
    mfa_forcast         NUMERIC(11,2)[] NOT NULL DEFAULT ARRAY[]::NUMERIC[],

    -- Alternate key (MFA-ALT-KEY1 = mfa_dept + mfa_gan1)
    mfa_dept            CHAR(6)     NOT NULL DEFAULT '000000',
    mfa_gan1            CHAR(12)    NOT NULL DEFAULT '            ',

    CONSTRAINT pk_mfa PRIMARY KEY (mfa_gan)
);

CREATE INDEX IF NOT EXISTS idx_mfa_alt_key1
    ON mfa (mfa_dept, mfa_gan1);
