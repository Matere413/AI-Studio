import styles from "@/features/generation/components/GenerationStudio.module.css";

interface FileThumbProps {
  name: string;
  url: string;
}

export default function FileThumb({ name, url }: FileThumbProps) {
  return (
    <figure className={styles.fileThumb}>
      <img className={styles.fileThumbImage} src={url} alt={name} />
      <figcaption className={styles.fileThumbName}>{name}</figcaption>
    </figure>
  );
}
