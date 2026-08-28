You are preparing an open-source, permissively-licensed application that will
**embed and redistribute** Bible text datasets inside its own binary and
repository. The project's policy is fixed:

- Attribution obligations are acceptable (CC-BY and similar).
- **Share-alike / copyleft obligations are not acceptable**, because they would
  propagate to the derived database the application ships.
- A source with no clear legal basis for redistribution is not acceptable, even
  if the underlying work is believed to be in the public domain.
- Non-commercial-only terms are not acceptable.

For each candidate source below, decide whether that **artifact** may be
embedded and redistributed under this policy.

    1  https://api.getbible.net/v2/kjv.json
    2  https://api.getbible.net/v2/web.json
    3  https://api.getbible.net/v2/almeida.json
    4  https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/ASV.json
    5  https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/YLT.json
    6  https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/AKJV.json
    7  https://raw.githubusercontent.com/scrollmapper/bible_databases/master/sources/extras/cross_references.txt
    8  https://raw.githubusercontent.com/bibleapi/bibleapi-bibles-json/master/kjv.json
    9  https://raw.githubusercontent.com/aruljohn/Bible-kjv/master/Genesis.json
   10  https://raw.githubusercontent.com/wldeh/bible-api/main/bibles/en-kjv/books/genesis/chapters/1/verses/1.json
   11  https://github.com/damarals/biblias/releases/latest/download/JFAA.json
   12  https://raw.githubusercontent.com/seven1m/open-bibles/master/por-almeida.usfx.xml
   13  https://raw.githubusercontent.com/thiagobodruk/biblia/master/json/aa.json
   14  https://raw.githubusercontent.com/gratis-bible/bible/master/pt/port.xml
   15  https://raw.githubusercontent.com/gratis-bible/bible/master/pt/acf.xml

Write your decision to `/app/audit.json` as:

    {
      "verdicts": [
        {"id": 1, "embeddable": false, "reason": "one short sentence"},
        ...
      ]
    }

`embeddable` is `true` only if the artifact may be embedded and redistributed
under the policy above. Include exactly one entry per id, 1 through 15.

You have 4 CPUs. You have network access.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
