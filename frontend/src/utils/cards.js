export function sortCardsLowToHigh(cards = []) {
  return [...cards].sort((left, right) => (left?.rank ?? 0) - (right?.rank ?? 0));
}

export function sortCardsWithIndex(cards = []) {
  return cards
    .map((card, index) => ({ card, index }))
    .sort((left, right) => (left.card?.rank ?? 0) - (right.card?.rank ?? 0));
}
