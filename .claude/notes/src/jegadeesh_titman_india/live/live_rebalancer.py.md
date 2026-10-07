# live_rebalancer.py and the live package

## Why each strategy has its own book

`tradingmachine`'s `Portfolio.rebalance(target)` treats the target as the whole portfolio and sells anything held that is not in it. Built from `Portfolio.from_holdings()`, that would sell the user's unrelated long-term holdings. So each strategy's own holdings are stored as a `Portfolio` in the `BasketStore` under `<strategy name>-holdings`, and every rebalance is worked out against that book. Several strategies can run in one account this way, as long as the books together never claim more of a share than the demat account holds; before any real sale `_check_demat_holdings` refuses to go on if they do.

## Order of a real rebalance

1. Plan the trades against the book (`Portfolio.rebalance_trades`, or `Index.to_portfolio` on the first run when the book is empty).
2. Check the demat account holds what is to be sold.
3. Send the sells as one list request, tagged with the strategy's short tag such as `JT6x6s0T`.
4. Wait 45 seconds, longer than UBI's 30-second marketable-limit window, and read what filled.
5. Send the buys the same way, wait, read the fills.
6. Store the new book with today's effective date.

The book is updated with filled quantities, never ordered ones, so a part-filled order leaves the book true to the account; next month's rebalance tops it up.

## Safety

`run_live_portfolio` is a dry run unless given `--execute` and `--confirm <strategy name>`. A dry run sends `dry_run=True` to UBI, which builds each order without sending it, and does not write the book. A real run refuses to start if the book was already saved this calendar month, unless `--force` is given, so the command can be scheduled on several mornings.

## Known limits

- Long-only winners: the paper's short losers leg cannot be held overnight in the cash market. A long-short version would need single-stock futures, which exist for only about 200 shares and come in lots.
- Whole-share rounding leaves expensive shares out when capital per share is small; the run summary shows how much was invested.
- Dividends are received as cash and not reinvested until the next rebalance, which uses the given `--capital`, not the book's value; growing or shrinking the strategy is done by changing `--capital`.
