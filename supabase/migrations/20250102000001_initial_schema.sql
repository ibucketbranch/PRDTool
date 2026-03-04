-- Conversation Analysis Database Schema
-- Designed for analyzing long-term relationship conversations

-- Participants table
CREATE TABLE participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    identifier TEXT UNIQUE, -- e.g., "Person A", "Person B", or actual names if available
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages/Exchanges table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    message_date TIMESTAMPTZ,
    message_order INTEGER, -- Order within the conversation
    source_page INTEGER, -- PDF page number if applicable
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation threads/exchanges (grouping related messages)
CREATE TABLE exchanges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_date TIMESTAMPTZ,
    topic TEXT,
    participant_1_id UUID REFERENCES participants(id),
    participant_2_id UUID REFERENCES participants(id),
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Message sentiment and emotional markers
CREATE TABLE message_sentiment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    sentiment_score NUMERIC, -- -1 (negative) to 1 (positive)
    emotional_tone TEXT[], -- Array of emotions: anger, sadness, joy, fear, etc.
    intensity NUMERIC, -- 0 to 1
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Therapist-style analysis for individual participants
CREATE TABLE participant_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
    analysis_type TEXT, -- 'communication_style', 'emotional_patterns', 'conflict_resolution', etc.
    analysis_text TEXT NOT NULL,
    key_insights TEXT[],
    concerns TEXT[],
    strengths TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Relationship analysis (analysis of both together)
CREATE TABLE relationship_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_type TEXT, -- 'communication_dynamics', 'conflict_patterns', 'relationship_health', 'survival_assessment'
    analysis_text TEXT NOT NULL,
    key_insights TEXT[],
    red_flags TEXT[],
    positive_indicators TEXT[],
    survival_probability NUMERIC, -- 0 to 1 (probability they survived the marriage)
    survival_assessment TEXT, -- 'likely_survived', 'likely_ended', 'uncertain'
    time_period_start TIMESTAMPTZ,
    time_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Key themes and topics identified in the conversation
CREATE TABLE themes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    theme_name TEXT NOT NULL,
    description TEXT,
    frequency INTEGER DEFAULT 0,
    first_occurrence TIMESTAMPTZ,
    last_occurrence TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Message-theme associations
CREATE TABLE message_themes (
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    theme_id UUID REFERENCES themes(id) ON DELETE CASCADE,
    PRIMARY KEY (message_id, theme_id)
);

-- Timeline events (significant moments in the relationship)
CREATE TABLE timeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date TIMESTAMPTZ,
    event_type TEXT, -- 'conflict', 'resolution', 'milestone', 'crisis', etc.
    description TEXT NOT NULL,
    participants_involved UUID[], -- Array of participant IDs
    significance_level TEXT, -- 'low', 'medium', 'high', 'critical'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Communication patterns analysis
CREATE TABLE communication_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type TEXT, -- 'response_time', 'message_length', 'topic_avoidance', etc.
    participant_id UUID REFERENCES participants(id) ON DELETE CASCADE,
    pattern_description TEXT NOT NULL,
    frequency NUMERIC,
    trend TEXT, -- 'increasing', 'decreasing', 'stable'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_messages_participant ON messages(participant_id);
CREATE INDEX idx_messages_date ON messages(message_date);
CREATE INDEX idx_messages_order ON messages(message_order);
CREATE INDEX idx_message_sentiment_message ON message_sentiment(message_id);
CREATE INDEX idx_participant_analysis_participant ON participant_analysis(participant_id);
CREATE INDEX idx_timeline_events_date ON timeline_events(event_date);
CREATE INDEX idx_exchanges_date ON exchanges(exchange_date);

-- Enable Row Level Security (optional, can be configured later)
ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE exchanges ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_sentiment ENABLE ROW LEVEL SECURITY;
ALTER TABLE participant_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationship_analysis ENABLE ROW LEVEL SECURITY;
ALTER TABLE themes ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_themes ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE communication_patterns ENABLE ROW LEVEL SECURITY;

-- Create a policy to allow all operations (for local development)
-- In production, you'd want more restrictive policies
CREATE POLICY "Allow all operations" ON participants FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON messages FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON exchanges FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON message_sentiment FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON participant_analysis FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON relationship_analysis FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON themes FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON message_themes FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON timeline_events FOR ALL USING (true);
CREATE POLICY "Allow all operations" ON communication_patterns FOR ALL USING (true);
