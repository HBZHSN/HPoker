/**
 * Return whether the table should render a second run-it-twice board.
 *
 * The RIT voting screen does not mean that a second board was agreed to:
 * until every contender votes, the final mode is still undecided.
 */
export function hasSecondCommunityBoard({
  ritEnabled = false,
  boardCards2 = [],
  boardCards2Full = [],
} = {}) {
  return Boolean(
    ritEnabled ||
    boardCards2.length > 0 ||
    boardCards2Full.length > 0
  );
}
