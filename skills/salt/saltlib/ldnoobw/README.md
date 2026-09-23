# LDNOOBW word lists

These files are the "List of Dirty, Naughty, Obscene, and Otherwise Bad Words"
by Shutterstock and contributors.

- Source: <https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words>
- Commit: `5faf2ba42d7b1c0977169ec3611df25a3c08eb13` (2020-07-13)
- License: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/),
  full text in [LICENSE](LICENSE)

Changes: the language files are unmodified. The Klingon list (`tlh`) is not
included. At runtime, salt merges these lists with its own words in
`../words.toml` and skips the entries listed under `triggers.exclude` there.

Warning: these lists contain material that many people find offensive.
