--
-- PostgreSQL database dump
--

-- Dumped from database version 14.15 (Homebrew)
-- Dumped by pg_dump version 14.15 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: participants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.participants (
    uuid uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    connected_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: transcripts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcripts (
    id integer NOT NULL,
    participant_id uuid NOT NULL,
    transcript text NOT NULL,
    recorded_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: transcripts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transcripts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transcripts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transcripts_id_seq OWNED BY public.transcripts.id;


--
-- Name: transcripts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcripts ALTER COLUMN id SET DEFAULT nextval('public.transcripts_id_seq'::regclass);


--
-- Name: participants participants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.participants
    ADD CONSTRAINT participants_pkey PRIMARY KEY (uuid);


--
-- Name: transcripts transcripts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcripts
    ADD CONSTRAINT transcripts_pkey PRIMARY KEY (id);


--
-- Name: idx_participants_connected_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_participants_connected_at ON public.participants USING btree (connected_at);


--
-- Name: idx_transcripts_participant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcripts_participant_id ON public.transcripts USING btree (participant_id);


--
-- Name: idx_transcripts_recorded_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcripts_recorded_at ON public.transcripts USING btree (recorded_at);


--
-- Name: participants update_participants_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_participants_updated_at BEFORE UPDATE ON public.participants FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: transcripts update_transcripts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_transcripts_updated_at BEFORE UPDATE ON public.transcripts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: transcripts transcripts_participant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcripts
    ADD CONSTRAINT transcripts_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES public.participants(uuid);


--
-- PostgreSQL database dump complete
--

