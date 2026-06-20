import { forwardRef, type ButtonHTMLAttributes, type PropsWithChildren } from "react";
import styles from "@/features/generation/components/GenerationStudio.module.css";

type IconButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>;

const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { children, className, type = "button", ...props },
  ref
) {
  const mergedClassName = [styles.iconButton, className].filter(Boolean).join(" ");

  return (
    <button ref={ref} className={mergedClassName} type={type} {...props}>
      {children}
    </button>
  );
});

export default IconButton;
