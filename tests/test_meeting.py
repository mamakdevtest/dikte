"""A two-channel recording turned into minutes.

Attribution is settled by the channels rather than guessed, so the tests care
about what happens at the seams: the microphone picking the other side up
through the speakers, two people talking over each other, and a run that died
after the transcription and must not pay for it twice.
"""

import contextlib
import os
import time
import unittest
import wave
from unittest import mock

import api
import cleanup
import config as cfg
import i18n
import meeting
from tests.support import DikteTest, make_wav, silence, speech, stereo, tone
from tests.test_cleanup import gateway


def seg(start, end, text, speaker):
    return (start, end, text, speaker)


class SplitChannels(DikteTest):
    def stereo_file(self, left, right, name="meeting.wav"):
        return make_wav(self.path(name), stereo(left, right), channels=2)

    def test_the_two_sides_come_out_as_separate_files(self):
        path = self.stereo_file(tone(1.0, amplitude=16000), silence(1.0))
        mine, theirs = meeting.split_channels(path, self.root)
        for side in (mine, theirs):
            with contextlib.closing(wave.open(side, "rb")) as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getnframes(), 16000)

    def test_the_left_channel_is_mine(self):
        path = self.stereo_file(tone(1.0, amplitude=16000), silence(1.0))
        mine, theirs = meeting.split_channels(path, self.root)
        self.assertGreater(max(meeting.rms_series(mine)), 0.1)
        self.assertEqual(max(meeting.rms_series(theirs)), 0.0)

    def test_a_recording_longer_than_the_read_block(self):
        path = self.stereo_file(tone(3.0), silence(3.0))
        mine, _ = meeting.split_channels(path, self.root)
        with contextlib.closing(wave.open(mine, "rb")) as wav:
            self.assertEqual(wav.getnframes(), 3 * 16000)

    def test_a_dictation_is_not_a_meeting(self):
        path = make_wav(self.path("mono.wav"), silence(1.0))
        with self.assertRaises(api.ApiError):
            meeting.split_channels(path, self.root)


class RmsSeries(DikteTest):
    def test_silence_reads_as_nothing(self):
        path = make_wav(self.path("quiet.wav"), silence(1.0))
        self.assertEqual(set(meeting.rms_series(path)), {0.0})

    def test_a_block_per_level_frame(self):
        path = make_wav(self.path("clip.wav"), silence(1.0))
        self.assertEqual(len(meeting.rms_series(path)),
                         -(-16000 // meeting.LEVEL_FRAMES))

    def test_a_loud_recording_reads_above_zero(self):
        path = make_wav(self.path("loud.wav"), tone(1.0, amplitude=16000))
        self.assertGreater(max(meeting.rms_series(path)), 0.1)

    def test_the_rate_is_read_off_the_file(self):
        path = make_wav(self.path("clip.wav"), silence(0.1), rate=8000)
        self.assertEqual(meeting.wav_rate(path), 8000)


class MergeTurns(unittest.TestCase):
    def test_one_timeline_out_of_two_channels(self):
        turns = meeting.merge_turns([
            seg(5.0, 6.0, "and you?", "theirs"),
            seg(0.0, 1.0, "hello", "mine"),
        ])
        self.assertEqual([(start, speaker) for start, speaker, _ in turns],
                         [(0.0, "mine"), (5.0, "theirs")])

    def test_one_person_carrying_on_stays_one_turn(self):
        turns = meeting.merge_turns([
            seg(0.0, 1.0, "hello", "mine"),
            seg(1.2, 2.0, "how are you", "mine"),
        ])
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0][2], "hello how are you")

    def test_a_long_pause_starts_a_new_line(self):
        turns = meeting.merge_turns([
            seg(0.0, 1.0, "hello", "mine"),
            seg(20.0, 21.0, "still there?", "mine"),
        ])
        self.assertEqual(len(turns), 2)

    def test_the_gap_is_measured_from_the_end_of_the_last_words(self):
        turns = meeting.merge_turns([
            seg(0.0, 10.0, "a long sentence", "mine"),
            seg(15.0, 16.0, "and another", "mine"),
        ])
        self.assertEqual(len(turns), 1)

    def test_the_speaker_changing_always_starts_a_new_turn(self):
        turns = meeting.merge_turns([
            seg(0.0, 1.0, "hello", "mine"),
            seg(1.1, 2.0, "hi", "theirs"),
        ])
        self.assertEqual(len(turns), 2)

    def test_my_microphone_hearing_them_through_the_speakers_is_dropped(self):
        turns = meeting.merge_turns([
            seg(0.0, 2.0, "we should ship it on Friday", "theirs"),
            seg(0.1, 2.0, "we should ship it on friday", "mine"),
        ])
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0][1], "theirs")

    def test_talking_over_each_other_is_not_an_echo(self):
        turns = meeting.merge_turns([
            seg(0.0, 2.0, "we should ship it on Friday", "theirs"),
            seg(0.1, 2.0, "no, next week is better", "mine"),
        ])
        self.assertEqual(len(turns), 2)

    def test_the_same_sentence_said_later_is_not_an_echo(self):
        turns = meeting.merge_turns([
            seg(0.0, 2.0, "ship it on Friday", "theirs"),
            seg(30.0, 32.0, "ship it on Friday", "mine"),
        ])
        self.assertEqual(len(turns), 2)

    def test_a_side_that_transcribed_to_nothing_is_dropped(self):
        turns = meeting.merge_turns([
            seg(0.0, 1.0, "...", "mine"),
            seg(2.0, 3.0, "hello", "theirs"),
        ])
        self.assertEqual(len(turns), 1)

    def test_nothing_was_said_at_all(self):
        self.assertEqual(meeting.merge_turns([]), [])


class RenderTurns(unittest.TestCase):
    def test_a_stamp_and_a_name_per_line(self):
        text = meeting.render_turns(
            [(0.0, "mine", "hello"), (65.0, "theirs", " hi ")], "Yusuf", "Ayşe")
        self.assertEqual(text, "[00:00] Yusuf: hello\n[01:05] Ayşe: hi")

    def test_nothing_to_render(self):
        self.assertEqual(meeting.render_turns([], "Me", "Them"), "")


class Document(DikteTest):
    def test_a_heading_becomes_the_title(self):
        self.assertEqual(meeting.split_title("# Kickoff\n\nWe agreed."),
                         ("Kickoff", "We agreed."))

    def test_minutes_that_open_with_prose_have_no_title(self):
        self.assertEqual(meeting.split_title("We agreed to ship."),
                         ("", "We agreed to ship."))

    def test_nothing_written(self):
        self.assertEqual(meeting.split_title(""), ("", ""))
        self.assertEqual(meeting.split_title(None), ("", ""))

    def test_the_document_carries_the_title_the_date_and_the_length(self):
        text = meeting.build_document("Kickoff", "2026-08-01 10:00", 3900,
                                      "We agreed.", "[00:00] Me: hello")
        self.assertTrue(text.startswith("# Kickoff"))
        self.assertIn("Date: 1 August 2026 10:00", text)
        self.assertIn("Duration: 1 h 5 min", text)

    def test_participants_join_the_header_when_expected(self):
        text = meeting.build_document("Kickoff", "2026-08-01 10:00", 3900,
                                      "We agreed.", "[00:00] Me: hello",
                                      participants="Yusuf, Ayşe")
        self.assertIn("Participants: Yusuf, Ayşe", text)
        plain = meeting.build_document("Kickoff", "2026-08-01 10:00", 3900,
                                       "", "[00:00] Me: hello")
        self.assertNotIn("Participants", plain)

    def test_the_header_hides_itself_behind_a_dateless_entry(self):
        text = meeting.build_document("Kickoff", "", 60, "", "[00:00] Me: hi")
        self.assertIn("Duration: 1 min", text)
        self.assertNotIn("Date", text)

    def test_the_transcript_can_be_read_back_out(self):
        transcript = "[00:00] Me: hello\n[00:05] Other side: hi"
        text = meeting.build_document("Kickoff", "now", 60, "We agreed.", transcript)
        self.assertEqual(meeting.read_transcript(text), transcript)

    def test_a_document_with_no_minutes_yet_still_gives_its_transcript_back(self):
        transcript = "[00:00] Me: hello"
        text = meeting.build_document("Kickoff", "now", 60, "", transcript)
        self.assertEqual(meeting.read_transcript(text), transcript)

    def test_a_document_written_by_something_else(self):
        self.assertEqual(meeting.read_transcript("# Notes\n\nJust prose."), "")

    def test_the_marker_is_a_comment_so_it_never_renders(self):
        self.assertTrue(meeting.TRANSCRIPT_MARKER.startswith("<!--"))

    def test_the_length_reads_as_minutes_under_an_hour(self):
        self.assertEqual(meeting.length_label(0), "0 min")
        self.assertEqual(meeting.length_label(3540), "59 min")

    def test_the_length_reads_as_hours_past_one(self):
        self.assertEqual(meeting.length_label(3600), "1 h 0 min")
        self.assertEqual(meeting.length_label(7325), "2 h 2 min")

    def test_the_length_is_translated(self):
        self.write_config({"ui_language": "tr"})
        cfg.Config()
        self.assertIn("dk", meeting.length_label(600))


class When(unittest.TestCase):
    """The date a meeting carries, said the way people write it."""

    def test_english_uses_the_english_calendar(self):
        self.assertEqual(meeting.format_when("2026-08-01 14:30"),
                         "1 August 2026 14:30")
        self.assertEqual(meeting.format_when("2026-08-01 14:30", short=True),
                         "1 Aug 2026 14:30")

    def test_turkish_uses_the_turkish_calendar(self):
        i18n.set_language("tr")
        self.addCleanup(i18n.set_language, "en")
        self.assertEqual(meeting.format_when("2026-08-01 14:30"),
                         "1 Ağustos 2026 14:30")
        self.assertEqual(meeting.format_when("2026-08-01 14:30", short=True),
                         "1 Ağu 2026 14:30")

    def test_an_unparseable_stamp_comes_back_as_it_arrived(self):
        self.assertEqual(meeting.format_when(""), "")
        self.assertEqual(meeting.format_when("yesterday"), "yesterday")
        self.assertEqual(meeting.format_when(None), "")

    def test_the_fallback_title_names_the_day(self):
        self.assertEqual(meeting.fallback_title("2026-08-01 14:30"),
                         "Meeting — 1 Aug 2026 14:30")
        self.assertEqual(meeting.fallback_title(""), "Meeting")


class CleanTitle(unittest.TestCase):
    def test_quotes_markup_and_whitespace_go(self):
        self.assertEqual(meeting.clean_title(' "# Kickoff"\n\n '), "Kickoff")
        self.assertEqual(meeting.clean_title("- Weekly sync."), "Weekly sync")
        self.assertEqual(meeting.clean_title("„Toplantı“"), "Toplantı")

    def test_newlines_become_one_line(self):
        self.assertEqual(meeting.clean_title("Kickoff\nplanning\nsession"),
                         "Kickoff planning session")

    def test_overlong_titles_are_cut_on_a_word(self):
        title = meeting.clean_title(" ".join(["word"] * 30))
        self.assertLessEqual(len(title), meeting.TITLE_MAX)
        self.assertTrue(title.split()[-1] == "word")

    def test_nothing_left_means_nothing(self):
        self.assertEqual(meeting.clean_title('"""'), "")
        self.assertEqual(meeting.clean_title(""), "")
        self.assertEqual(meeting.clean_title(None), "")


class Entry(unittest.TestCase):
    def test_the_stem_is_a_sortable_timestamp(self):
        base = meeting.new_base()
        self.assertEqual(len(base), 15)
        self.assertEqual(base[8], "-")

    def test_a_fresh_row_reads_its_date_back_out_of_the_stem(self):
        entry = meeting.new_entry("20260801-143000", 125.44)
        self.assertEqual(entry["base"], "20260801-143000")
        self.assertEqual(entry["ts"], "2026-08-01 14:30")
        self.assertEqual(entry["duration"], 125.4)
        self.assertEqual(entry["status"], "recorded")


class Pipeline(DikteTest):
    """The chain, with the transcription and the two cleanup calls faked."""

    def setUp(self):
        super().setUp()
        # The local defaults are kept for the two tests that cover them; the
        # rest hold the hosted road — a user-added gateway — which the mocked
        # api.cleanup answers either way.
        self.conf = self.config(
            providers=[gateway(models={"text": "some/cleanup",
                                        "minutes": "some/minutes"})],
            cleanup_provider="user/abc123", meeting_provider="user/abc123",
            # The shipped default keeps recordings; the audio-goes test below
            # is about the discard road, so it pins the old behavior here.
            meeting_keep_audio=False)
        self.base = "20260801-100000"
        self.doc, self.wav = cfg.meeting_paths(self.base)
        self.wav.parent.mkdir(parents=True, exist_ok=True)
        make_wav(self.wav, stereo(speech(2.0), speech(2.0, freq=220.0)), channels=2)
        cfg.save_meeting(meeting.new_entry(self.base, 1.0))

    def run_pipeline(self, entry=None, segments=None, minutes="# Kickoff\n\nAgreed.",
                     title="Kickoff", cleanup_fails=False):
        worker = meeting.MeetingPipeline(self.conf)
        done, failures = [], []
        worker.finished.connect(lambda *args: done.append(args))
        worker.failed.connect(lambda *args: failures.append(args))

        def cleanup(text, *args, **kwargs):
            if cleanup_fails:
                raise api.ApiError("the gateway is rate limiting you")
            prompt = args[2] if len(args) > 2 else kwargs.get("prompt", "")
            if "professional title" in prompt:
                return title
            return minutes

        with mock.patch.object(api, "transcribe_segments",
                               return_value=segments or [(0.0, 1.0, "hello")]), \
                mock.patch.object(api, "cleanup", side_effect=cleanup):
            # Run in this thread: the signals would otherwise be queued and
            # never delivered without an event loop.
            worker._work(entry or cfg.read_meetings()[0])
        return done, failures

    def test_a_recording_becomes_a_document(self):
        done, failures = self.run_pipeline()
        self.assertEqual(failures, [])
        self.assertEqual(done[0], (self.base, "Kickoff"))
        self.assertIn("Agreed.", self.doc.read_text(encoding="utf-8"))

    def test_a_gateway_answers_the_minutes_when_chosen(self):
        """The registry road: the entry's key, address and minutes model, and
        its name in an error's mouth."""
        self.conf["meeting_cleanup"] = False
        with mock.patch.object(api, "transcribe_segments",
                               return_value=[(0.0, 1.0, "hello")]), \
                mock.patch.object(api, "cleanup",
                                  return_value="# Kickoff\n\nAgreed.") as call:
            meeting.MeetingPipeline(self.conf)._work(cfg.read_meetings()[0])
        key, model = call.call_args.args[1:3]
        self.assertEqual((key, model), ("sk-gw-test", "some/minutes"))
        self.assertEqual(call.call_args.kwargs["base_url"],
                         "https://gw.example/v1")
        self.assertEqual(call.call_args.kwargs["provider"], "user/abc123")
        self.assertEqual(call.call_args.kwargs["service"], "Gateway")
        self.assertEqual(cfg.read_meetings()[0]["model"], "some/minutes")

    def test_a_gateway_with_no_minutes_model_fails_loudly(self):
        self.conf["providers"] = [gateway(models={"text": "some/cleanup"})]
        self.conf["meeting_cleanup"] = False
        with mock.patch.object(api, "transcribe_segments",
                               return_value=[(0.0, 1.0, "hello")]):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *args: failures.append(args))
            worker._work(cfg.read_meetings()[0])
        self.assertIn("Settings", failures[0][1])
        # Minutes failure after transcript checkpoint keeps transcribed (retry reuses transcript)
        self.assertEqual(cfg.read_meetings()[0]["status"], "transcribed")

    def test_a_provider_none_of_the_roads_knows_is_a_dead_end(self):
        """The CLIs are not offered the job; a name that lands here anyway
        fails loudly rather than quietly re-routing the meeting."""
        self.conf["meeting_provider"] = "claude"
        with self.assertRaises(api.ApiError):
            meeting.MeetingPipeline(self.conf)._minutes("[00:00] Me: hello")

    def test_the_local_model_writes_the_minutes_when_chosen(self):
        """The default: llama.cpp on this machine, the same road a local
        cleanup takes — no key, no bill, and the meeting prompt not the
        cleanup one."""
        self.conf["meeting_provider"] = "local"
        self.conf["local_llm_model"] = "gemma-3-4b-it-Q4_K_M.gguf"
        self.conf["meeting_cleanup"] = False

        def local(text, conf, prompt, timeout, aborter=None):
            if "professional title" in prompt:
                return "Kickoff"
            return "# Kickoff\n\nAgreed."

        with mock.patch.object(api, "transcribe_segments",
                               return_value=[(0.0, 1.0, "hello")]), \
                mock.patch.object(cleanup, "_local",
                                  side_effect=local) as call:
            meeting.MeetingPipeline(self.conf)._work(cfg.read_meetings()[0])
        text, conf, prompt, timeout = call.call_args.args
        self.assertEqual(prompt, self.conf.meeting_prompt())
        self.assertEqual(timeout, 600)
        row = cfg.read_meetings()[0]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["title"], "Kickoff")
        # The history names the model that actually wrote them.
        self.assertEqual(row["model"], "gemma-3-4b-it-Q4_K_M.gguf")

    def test_the_row_ends_up_done_with_its_title(self):
        self.run_pipeline()
        row = cfg.read_meetings()[0]
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["title"], "Kickoff")

    def test_the_audio_goes_once_the_minutes_are_written(self):
        self.run_pipeline()
        self.assertFalse(self.wav.exists())

    def test_the_audio_is_kept_when_the_setting_says_so(self):
        self.conf["meeting_keep_audio"] = True
        self.run_pipeline()
        self.assertTrue(self.wav.exists())

    def test_a_failed_run_keeps_the_audio_whatever_the_setting_says(self):
        """It is the only copy of the meeting, and a retry starts from it."""
        _, failures = self.run_pipeline(cleanup_fails=True)
        self.assertTrue(self.wav.exists())
        self.assertEqual(failures[0][0], self.base)
        self.assertEqual(cfg.read_meetings()[0]["status"], "failed")

    def test_a_retry_does_not_transcribe_the_hour_again(self):
        self.conf["meeting_cleanup"] = False
        self.run_pipeline(cleanup_fails=True)
        entry = cfg.read_meetings()[0]
        # Minutes-stage failure with transcript checkpoint keeps transcribed
        self.assertEqual(entry["status"], "transcribed")

        with mock.patch.object(api, "transcribe_segments") as transcribe, \
                mock.patch.object(api, "cleanup", return_value="# Kickoff\n\nAgreed."):
            worker = meeting.MeetingPipeline(self.conf)
            worker._work(dict(entry))
        transcribe.assert_not_called()
        self.assertEqual(cfg.read_meetings()[0]["status"], "done")

    def test_a_recording_that_is_gone(self):
        self.wav.unlink()
        _, failures = self.run_pipeline()
        self.assertIn("gone", failures[0][1])

    def test_the_silence_gate_gets_a_second_opinion(self):
        """Every chunk judged quiet, yet the file carries sound: the loudest
        part of each side gets one call before an hour is declared speechless."""
        with mock.patch.object(meeting.MeetingPipeline, "_silent",
                               return_value=True):
            done, failures = self.run_pipeline()
        self.assertEqual(failures, [])
        self.assertEqual(done[0][0], self.base)
        self.assertTrue(self.doc.exists())

    def test_a_silent_recording_names_the_devices(self):
        """A wrong device records a faithful file full of nothing, and the
        failure has to send the user to the sound page, not the speech one."""
        make_wav(self.wav, stereo(silence(2.0), silence(2.0)), channels=2)
        with mock.patch.object(api, "transcribe_segments", return_value=[]), \
                mock.patch.object(api, "cleanup", return_value="# Kickoff"):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        self.assertIn("silent", failures[0][1])

    def test_recordings_past_the_retention_go(self):
        old, fresh = cfg.MEETINGS_DIR / "old.wav", cfg.MEETINGS_DIR / "new.wav"
        cfg.MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
        for wav in (old, fresh):
            wav.write_bytes(b"")
        week_ago = time.time() - 8 * 86400
        os.utime(old, (week_ago, week_ago))
        self.assertEqual(meeting.prune_audio(7), 1)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
        # Zero means nothing is ever old enough to leave.
        self.assertEqual(meeting.prune_audio(0), 0)
        self.assertTrue(fresh.exists())

    def test_the_transcript_is_attributed_by_channel(self):
        self.conf["meeting_self_name"] = "Yusuf"
        self.conf["meeting_other_name"] = "Ayşe"
        self.conf["meeting_cleanup"] = False
        sides = iter([[(0.0, 1.0, "shall we ship it")],
                      [(2.0, 3.0, "next week is better")]])
        with mock.patch.object(api, "transcribe_segments",
                               side_effect=lambda *a, **k: next(sides)), \
                mock.patch.object(api, "cleanup", return_value="# Kickoff\n\nAgreed."):
            meeting.MeetingPipeline(self.conf)._work(cfg.read_meetings()[0])
        transcript = meeting.read_transcript(self.doc.read_text(encoding="utf-8"))
        self.assertEqual(transcript.splitlines(),
                         ["[00:00] Yusuf: shall we ship it",
                          "[00:02] Ayşe: next week is better"])

    def test_minutes_with_no_heading_fall_back_to_a_title(self):
        self.run_pipeline(minutes="We agreed to ship.", title="")
        row = cfg.read_meetings()[0]
        self.assertEqual(row["title"], "Meeting — 1 Aug 2026 10:00")

    def test_a_title_failure_still_writes_the_minutes_up(self):
        """A shy title model never costs the meeting its minutes."""
        def cleanup(text, *args, **kwargs):
            prompt = args[2] if len(args) > 2 else kwargs.get("prompt", "")
            if "professional title" in prompt:
                raise api.ApiError("no title today")
            return "# Kickoff\n\nAgreed."

        with mock.patch.object(api, "transcribe_segments",
                               return_value=[(0.0, 1.0, "hello")]), \
                mock.patch.object(api, "cleanup", side_effect=cleanup):
            worker = meeting.MeetingPipeline(self.conf)
            done, failures = [], []
            worker.finished.connect(lambda *a: done.append(a))
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        self.assertEqual(failures, [])
        self.assertEqual(len(done), 1)
        self.assertEqual(cfg.read_meetings()[0]["title"], "Kickoff")

    def test_a_second_run_while_one_is_going_is_refused(self):
        worker = meeting.MeetingPipeline(self.conf)
        worker._thread = mock.Mock(is_alive=lambda: True)
        self.assertFalse(worker.run({"base": self.base}))


class AutoLanguage(DikteTest):
    """Nothing pinned by hand: the recording says which language it is in.

    The probe hears the first stretch that carries speech, and the language
    it names rides along to every chunk after it — or the run stops there,
    because an hour sent through the wrong language is worse than none.
    """

    def setUp(self):
        super().setUp()
        self.conf = self.config(
            providers=[gateway(models={"text": "some/cleanup",
                                        "minutes": "some/minutes"})],
            cleanup_provider="user/abc123", meeting_provider="user/abc123",
            meeting_keep_audio=False, meeting_cleanup=False,
            language="auto", meeting_language="")
        self.base = "20260801-110000"
        self.doc, self.wav = cfg.meeting_paths(self.base)
        self.wav.parent.mkdir(parents=True, exist_ok=True)
        make_wav(self.wav, stereo(speech(2.0), speech(2.0, freq=220.0)),
                 channels=2)
        cfg.save_meeting(meeting.new_entry(self.base, 1.0))

    def test_the_detected_language_is_pinned_for_every_chunk(self):
        languages = []

        def fake_segments(target, path, language="", prompt="", **kwargs):
            languages.append(language)
            return [(0.0, 1.0, "merhaba")]

        with mock.patch.object(meeting.MeetingPipeline, "_silent",
                               return_value=False), \
                mock.patch.object(api, "transcribe_auto",
                                  return_value=([], "tr")) as probe, \
                mock.patch.object(api, "transcribe_segments",
                                  side_effect=fake_segments), \
                mock.patch.object(api, "cleanup",
                                  return_value="# Kickoff\n\nAgreed."):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        self.assertEqual(failures, [])
        # Each side is heard out on its own, because the two sides of a
        # meeting may not share a language.
        self.assertEqual(probe.call_count, 2)
        self.assertTrue(languages)
        self.assertEqual(set(languages), {"tr"})

    def test_an_undetectable_language_stops_the_run(self):
        with mock.patch.object(meeting.MeetingPipeline, "_silent",
                               return_value=False), \
                mock.patch.object(api, "transcribe_auto",
                                  return_value=([], "")) as probe, \
                mock.patch.object(api, "transcribe_segments") as segments, \
                mock.patch.object(api, "cleanup", return_value="# Kickoff"):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        # Both sides heard out before giving up: the failure rests on
        # listened audio, and the transcript never ran without a language.
        self.assertEqual(probe.call_count, 2)
        segments.assert_not_called()
        self.assertEqual(failures[0][0], self.base)
        self.assertIn("could not be detected", failures[0][1])
        entry = cfg.read_meetings()[0]
        self.assertEqual(entry["status"], "failed")
        self.assertIn("could not be detected", entry["error"])

    def test_a_language_pinned_by_hand_never_probes(self):
        self.conf["language"] = "tr"
        with mock.patch.object(api, "transcribe_auto") as probe, \
                mock.patch.object(api, "transcribe_segments",
                                  return_value=[(0.0, 1.0, "hello")]), \
                mock.patch.object(api, "cleanup",
                                  return_value="# Kickoff\n\nAgreed."):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        probe.assert_not_called()
        self.assertEqual(failures, [])
        self.assertTrue(self.doc.exists())

    def test_each_side_keeps_the_language_it_was_pinned_to(self):
        self.conf["meeting_mine_language"] = "tr"
        self.conf["meeting_theirs_language"] = "en"
        by_side = {}

        def fake_segments(target, path, language="", prompt="", **kwargs):
            by_side.setdefault("mine" if "mine" in path else "theirs",
                               set()).add(language)
            return [(0.0, 1.0, "merhaba")]

        with mock.patch.object(meeting.MeetingPipeline, "_silent",
                               return_value=False), \
                mock.patch.object(api, "transcribe_auto") as probe, \
                mock.patch.object(api, "transcribe_segments",
                                  side_effect=fake_segments), \
                mock.patch.object(api, "cleanup",
                                  return_value="# Kickoff\n\nAgreed."):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        self.assertEqual(failures, [])
        probe.assert_not_called()
        self.assertEqual(by_side, {"mine": {"tr"}, "theirs": {"en"}})

    def test_a_pinned_side_is_never_probed_but_the_other_is(self):
        self.conf["meeting_mine_language"] = "tr"
        by_side = {}

        def fake_segments(target, path, language="", prompt="", **kwargs):
            by_side.setdefault("mine" if "mine" in path else "theirs",
                               set()).add(language)
            return [(0.0, 1.0, "merhaba")]

        with mock.patch.object(meeting.MeetingPipeline, "_silent",
                               return_value=False), \
                mock.patch.object(api, "transcribe_auto",
                                  return_value=([], "en")) as probe, \
                mock.patch.object(api, "transcribe_segments",
                                  side_effect=fake_segments), \
                mock.patch.object(api, "cleanup",
                                  return_value="# Kickoff\n\nAgreed."):
            worker = meeting.MeetingPipeline(self.conf)
            failures = []
            worker.failed.connect(lambda *a: failures.append(a))
            worker._work(cfg.read_meetings()[0])
        self.assertEqual(failures, [])
        probe.assert_called_once()
        self.assertEqual(by_side, {"mine": {"tr"}, "theirs": {"en"}})


class ResolveLanguages(DikteTest):
    """The language each side ends up transcribed in, without the pipeline."""

    def setUp(self):
        super().setUp()
        self.conf = self.config(language="auto", meeting_language="",
                                meeting_mine_language="",
                                meeting_theirs_language="")
        self.worker = meeting.MeetingPipeline(self.conf)
        self.sides = [("mine.wav", "mine", []), ("theirs.wav", "theirs", [])]

    def test_a_silent_side_borrows_the_other_sides_language(self):
        def probe(target, chunks, workdir, hint, offset=0):
            return "en" if offset else ""

        with mock.patch.object(self.worker, "_probe_language",
                               side_effect=probe):
            resolved = self.worker._resolve_languages(
                None, self.sides, self.root, "")
        self.assertEqual(resolved, {"mine": "en", "theirs": "en"})

    def test_no_answer_anywhere_stops_the_run(self):
        with mock.patch.object(self.worker, "_probe_language",
                               return_value=""):
            with self.assertRaises(api.ApiError):
                self.worker._resolve_languages(None, self.sides, self.root, "")

    def test_a_shared_meeting_language_covers_both_sides(self):
        self.conf["meeting_language"] = "de"
        with mock.patch.object(self.worker, "_probe_language") as probe:
            resolved = self.worker._resolve_languages(
                None, self.sides, self.root, "")
        self.assertEqual(resolved, {"mine": "de", "theirs": "de"})
        probe.assert_not_called()

    def test_a_side_overrides_the_shared_language(self):
        self.conf["meeting_language"] = "de"
        self.conf["meeting_theirs_language"] = "ar"
        with mock.patch.object(self.worker, "_probe_language") as probe:
            resolved = self.worker._resolve_languages(
                None, self.sides, self.root, "")
        self.assertEqual(resolved, {"mine": "de", "theirs": "ar"})
        probe.assert_not_called()


# --- retry helper (MeetingPipeline checkpoint coexistence) ---------------


class RetryHelper(DikteTest):
    """The convenience wrapper around MeetingPipeline's own checkpoint read."""

    def setUp(self):
        super().setUp()
        self.conf = self.config(
            providers=[gateway(models={"text": "some/cleanup",
                                         "minutes": "some/minutes"})],
            cleanup_provider="user/abc123", meeting_provider="user/abc123",
            meeting_keep_audio=True, meeting_cleanup=False)
        self.base = "20260802-120000"
        self.doc, self.wav = cfg.meeting_paths(self.base)
        self.wav.parent.mkdir(parents=True, exist_ok=True)
        make_wav(self.wav, stereo(speech(1.0), speech(1.0, freq=220.0)), channels=2)
        cfg.save_meeting(meeting.new_entry(self.base, 1.0))
        # Make the document look like a past run already reached the
        # status="transcribed" checkpoint (the body a retry resumes from).
        self.transcript = "[00:00] Me: hello world"
        self.doc.write_text(
            meeting.build_document("Kickoff", "2026-08-02 12:00", 60.0,
                                   "", self.transcript),
            encoding="utf-8")

    def test_retry_from_transcribed_skips_transcription(self):
        cfg.update_meeting(self.base, status="transcribed")
        with mock.patch.object(api, "transcribe_segments") as transcribe, \
             mock.patch.object(api, "cleanup", return_value="# Kickoff\n\nDone."):
            pipe = meeting.retry_meeting(self.base, self.conf)
            self.assertTrue(bool(pipe))
            # Wait for the background thread the helper started.
            pipe._thread.join(timeout=5)
        transcribe.assert_not_called()
        self.assertEqual(cfg.read_meetings()[0]["status"], "done")

    def test_retry_reads_the_stored_transcript_checkpoint(self):
        cfg.update_meeting(self.base, status="transcribed")
        seen_transcript = {}

        def fake_cleanup(text, *args, **kwargs):
            # The minutes call carries the stored transcript; capture it.
            prompt = args[2] if len(args) > 2 else kwargs.get("prompt", "")
            if "minutes" not in prompt.lower() and "tutanak" not in prompt.lower():
                # title path — ignore
                return "Kickoff"
            seen_transcript["text"] = text
            return "# Kickoff\n\nDone."

        with mock.patch.object(api, "transcribe_segments") as transcribe, \
             mock.patch.object(api, "cleanup", side_effect=fake_cleanup):
            pipe = meeting.retry_meeting(self.base, self.conf)
            pipe._thread.join(timeout=5)
        transcribe.assert_not_called()
        self.assertIn("hello world", seen_transcript.get("text", ""))

    def test_retry_entry_variant_accepts_a_dict(self):
        cfg.update_meeting(self.base, status="transcribed")
        entry = cfg.read_meetings()[0]
        with mock.patch.object(api, "transcribe_segments") as transcribe, \
             mock.patch.object(api, "cleanup", return_value="# Kickoff\n\nDone."):
            pipe = meeting.retry_meeting_entry(entry, self.conf)
            self.assertTrue(bool(pipe))
            pipe._thread.join(timeout=5)
        transcribe.assert_not_called()

    def test_retry_unknown_base_returns_false(self):
        self.assertFalse(meeting.retry_meeting("20990101-000000", self.conf))

    def test_retry_unknown_entry_dict_still_starts_from_that_dict(self):
        # retry_meeting_entry does not re-read the index; it trusts the dict.
        lonely = meeting.new_entry("20990101-000001", 1.0)
        with mock.patch.object(api, "transcribe_segments",
                                return_value=[(0.0, 1.0, "hi")]), \
             mock.patch.object(api, "cleanup", return_value="# Kickoff\n\nDone."):
            # Needs a wav for the recorded path; missing file is a failure
            # but the helper still started the pipeline and returned it.
            pipe = meeting.retry_meeting_entry(lonely, self.conf)
            self.assertTrue(bool(pipe))
            pipe._thread.join(timeout=5)
        # Finished via the failed path (no wav), but it did run.
        self.assertTrue(pipe is not False)


class Coexistence(DikteTest):
    """Meeting retry must not lose the transcript checkpoint.

    This is the coexistence-adjacent guarantee: a meeting that already
    reached status="transcribed" can be retried from that checkpoint while
    other audio activity (e.g. a concurrent dictation's history row) is
    untouched — the retry only touches the targeted base.
    """

    def setUp(self):
        super().setUp()
        self.conf = self.config(
            providers=[gateway(models={"text": "some/cleanup",
                                         "minutes": "some/minutes"})],
            cleanup_provider="user/abc123", meeting_provider="user/abc123",
            meeting_keep_audio=True, meeting_cleanup=False)
        self.base = "20260802-130000"
        self.doc, self.wav = cfg.meeting_paths(self.base)
        self.wav.parent.mkdir(parents=True, exist_ok=True)
        make_wav(self.wav, stereo(speech(1.0), silence(1.0)), channels=2)
        cfg.save_meeting(meeting.new_entry(self.base, 1.0))
        self.transcript = "[00:00] Me: coexistent"
        self.doc.write_text(
            meeting.build_document("Coexist", "2026-08-02 13:00", 60.0,
                                   "", self.transcript),
            encoding="utf-8")
        cfg.update_meeting(self.base, status="transcribed")

    def test_retry_leaves_other_meetings_alone(self):
        other = "20260802-140000"
        other_doc, other_wav = cfg.meeting_paths(other)
        other_wav.parent.mkdir(parents=True, exist_ok=True)
        make_wav(other_wav, stereo(silence(1.0), silence(1.0)), channels=2)
        cfg.save_meeting(meeting.new_entry(other, 1.0))
        before = {row["base"] for row in cfg.read_meetings()}

        with mock.patch.object(api, "transcribe_segments") as transcribe, \
             mock.patch.object(api, "cleanup", return_value="# Kickoff\n\nDone."):
            pipe = meeting.retry_meeting(self.base, self.conf)
            pipe._thread.join(timeout=5)
        transcribe.assert_not_called()
        after = {row["base"] for row in cfg.read_meetings()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
