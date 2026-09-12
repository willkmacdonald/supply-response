import outlookIcon from "../assets/product-icons/outlook_32x1.svg";
import teamsIcon from "../assets/product-icons/teams_32x1.svg";

export function SourceActionIcon({product}: {product: "outlook" | "teams"}) {
  return <img
    className="source-action-icon"
    src={product === "outlook" ? outlookIcon : teamsIcon}
    width={24}
    height={24}
    alt=""
    aria-hidden="true"
  />;
}
