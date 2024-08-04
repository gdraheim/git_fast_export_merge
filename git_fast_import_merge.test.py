#! /usr/bin/env python3

from unittest import main, TestCase
import git_fast_import_merge as app

tz1 = app.TimeZone(app.Plus(hours=1))
utc = app.TimeZone.utc
class time_from(TestCase):
   def test_000(self) -> None:
      have = app.time_from("foo")
      want = None
      self.assertEqual(want, have)
   def test_001(self) -> None:
      have = app.time_from("2022-12-01T23:34:45 +01:00")
      want = app.Time(2022,12,1, 23, 34, 45, tzinfo=tz1)
      self.assertEqual(want, have)
   def test_002(self) -> None:
      have = app.time_from("2022-12-01.23:34:45 +01:00")
      want = app.Time(2022,12,1, 23, 34, 45, tzinfo=tz1)
      self.assertEqual(want, have)
   def test_003(self) -> None:
      have = app.time_from("2022-12-01.23:34:45")
      want = app.Time(2022,12,1, 23, 34, 45, tzinfo=utc)
      self.assertEqual(want, have)
   def test_004(self) -> None:
      have = app.time_from("2022-12-01Z23:34:45")
      want = app.Time(2022,12,1, 23, 34, 45, tzinfo=utc)
      self.assertEqual(want, have)
   def test_005(self) -> None:
      want = app.Time(2022,12,1, 23, 34, 45, tzinfo=tz1)
      time = want.timestamp()
      spec = "%s +00:00" % int(time)
      have = app.time_from(spec)
      self.assertEqual(want, have)
   def test_006(self) -> None:
      want = app.Time(2022,12,1, 23, 34, 45, tzinfo=utc)
      time = want.timestamp()
      spec = "%s +01:00" % int(time)
      have = app.time_from(spec)
      self.assertEqual(want, have)

if __name__ == "__main__":
   main()

