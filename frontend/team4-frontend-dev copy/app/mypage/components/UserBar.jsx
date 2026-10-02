"use client";


/*import Image from "next/image";*/
import styles from "./UserBar.module.css";

export default function Userbar(){
  return(
    <div className={styles.box}>
      <p className={styles.name}>김컴공님</p>
      <p className={styles.student_id}>C000000</p>
      <p className={styles.major}>컴퓨터공학과</p>
      <div className={styles.sbox}></div>
    </div>
  )
}