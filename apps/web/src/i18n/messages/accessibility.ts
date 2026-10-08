import { defineMessages } from "../messages";

/** The accessibility coordinator line on the statement page (#26, standard 5568). */
export const accessibilityMessages = defineMessages({
  he: {
    coordinator: "רכזת הנגישות: {name}.",
    reach: "אפשר לפנות",
    byEmail: "בדוא״ל",
    byPhone: "בטלפון",
    or: "או",
    pending: "פרטי הקשר יפורסמו כאן לפני ההשקה.",
  },
  // TODO ar: copied from Hebrew, needs translation (#73).
  ar: {
    coordinator: "רכזת הנגישות: {name}.",
    reach: "אפשר לפנות",
    byEmail: "בדוא״ל",
    byPhone: "בטלפון",
    or: "או",
    pending: "פרטי הקשר יפורסמו כאן לפני ההשקה.",
  },
});
