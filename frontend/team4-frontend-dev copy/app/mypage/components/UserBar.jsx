"use client";


/*import Image from "next/image";*/
import styles from "./UserBar.module.css";

export default function Userbar({ profile }){
  return(
    <div className={styles.box}>
      <p className={styles.name}>{profile?.full_name ? `${profile.full_name}님` : "이름 미등록"}</p>
      <p className={styles.student_id}>{profile?.student_id ?? "학번 미등록"}</p>
      <p className={styles.major}>{profile?.major ?? "학과 미등록"}</p>
      <div className={styles.sbox}></div>
    </div>
  )
}