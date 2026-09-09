"""The one catalog-value rule: annual run rate x a 3-5x multiple band.

SOURCE OF TRUTH. Every surface that puts a dollar figure on the catalog
reads its multiples from here.

Three implementations used to disagree, and two of them were on pages a
label sees:

  valuation_engine.MULTIPLES          3 / 4 / 5   (/valuation, the money page)
  statements_engine.build_royalty_summary
                                      3 / 4 / 5   hardcoded a second time,
                                                  and read back by
                                                  epk_config.real_stats for
                                                  the press kit's
                                                  "Est. Catalog Value"
  royalty_data.CATALOG_VALUE_MULTIPLES
                                      8 / 12 / 16 read by /benchmark and by
                                                  the demo press kit

That last one is a defect, not a variant: the same account could be told
its catalog was worth 4x its run rate on /valuation and 12x on
/benchmark, three times the figure, with nothing on either page to say
which was meant. The money pages win, so 3/4/5 is the rule and the
8/12/16 band is gone.

3/4/5 is the conservative independent-catalog range report_builder
already quotes in the CSV a label receives, so the sheet and the page it
was quoted from cannot disagree either.
"""

MULTIPLES = {"low": 3, "mid": 4, "high": 5}


def band(annualized, multiples=None):
    """The low/mid/high value band for an annualised run rate."""
    multiples = multiples or MULTIPLES
    return {k: round(annualized * m) for k, m in multiples.items()}
