import { defineMessages } from "../messages";

/**
 * The line shown with every Arabic legal or consent text (privacy policy, consent sheets, beta
 * join, accessibility statement) until a lawyer has reviewed the Arabic. The Hebrew value exists
 * for the catalog's sake only: `LegalNotice` renders nothing in Hebrew.
 * Arabic machine-drafted, needs native-speaker review (#73).
 */
export const legalMessages = defineMessages({
  he: {
    translationNotice: "הנוסח העברי הוא המחייב",
  },
  ar: {
    translationNotice: "هذه ترجمة، والنص العبري هو الملزم",
  },
});
