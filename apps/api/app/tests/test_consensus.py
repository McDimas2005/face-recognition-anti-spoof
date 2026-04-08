from datetime import UTC, datetime, timedelta

from app.services.recognition import CandidateFrame, TemporalConsensusStore


def test_consensus_store_discards_old_frames():
    store = TemporalConsensusStore()
    old = datetime.now(UTC) - timedelta(seconds=10)
    new = datetime.now(UTC)

    store.add("session-1", "client-1", CandidateFrame(timestamp=old, person_id="person-1", similarity=0.9, second_score=0.1))
    frames = store.add("session-1", "client-1", CandidateFrame(timestamp=new, person_id="person-1", similarity=0.9, second_score=0.1))

    assert len(frames) == 1
    assert frames[0].timestamp == new

